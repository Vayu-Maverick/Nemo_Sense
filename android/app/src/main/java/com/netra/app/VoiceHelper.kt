package com.netra.app

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale
import java.util.UUID

/**
 * VoiceHelper — Manages Speech-to-Text (STT) and Text-to-Speech (TTS) for the
 * Netra blind guide app.
 *
 * STT: Uses Android's SpeechRecognizer API to capture voice commands.
 * TTS: Uses Android's TextToSpeech engine to speak responses and alerts.
 *
 * Features:
 *   • Plays a short beep before STT starts so the user knows to speak
 *   • Handles partial and final recognition results
 *   • TTS queue mode for sequential speech (e.g., navigation alerts)
 *   • Stops TTS when STT starts (prevents feedback loop)
 */
class VoiceHelper(private val context: Context, private val callback: VoiceCallback) {

    companion object {
        private const val TAG = "NetraVoice"
    }

    /**
     * Callback for voice events.
     */
    interface VoiceCallback {
        /** Called when the user's speech has been recognized. */
        fun onSpeechResult(text: String)

        /** Called with partial (interim) recognition results. */
        fun onPartialResult(text: String)

        /** Called when STT starts listening (mic is active). */
        fun onListeningStarted()

        /** Called when STT stops listening (mic is inactive). */
        fun onListeningStopped()

        /** Called when STT encounters an error. */
        fun onSpeechError(errorMessage: String)

        /** Called when TTS finishes speaking the current utterance. */
        fun onSpeakingFinished()
    }

    // ── Internals ───────────────────────────────────────────────────

    private var speechRecognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var isTtsReady = false
    private var isListening = false
    private var toneGenerator: ToneGenerator? = null

    // ── Initialization ──────────────────────────────────────────────

    /**
     * Initializes both TTS and STT engines. Call once in onCreate.
     */
    fun initialize() {
        initTts()
        initStt()
        initToneGenerator()
    }

    /**
     * Initializes the Text-to-Speech engine.
     * Sets language to English (US) for clear pronunciation.
     */
    private fun initTts() {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val result = tts?.setLanguage(Locale.US)
                if (result == TextToSpeech.LANG_MISSING_DATA ||
                    result == TextToSpeech.LANG_NOT_SUPPORTED
                ) {
                    Log.e(TAG, "TTS: English (US) not supported, trying default")
                    tts?.setLanguage(Locale.getDefault())
                }
                // Set slightly slower speech rate for blind users to catch everything
                tts?.setSpeechRate(0.9f)
                tts?.setPitch(1.0f)

                // Set up utterance listener to know when speech finishes
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        Log.d(TAG, "TTS started: $utteranceId")
                    }

                    override fun onDone(utteranceId: String?) {
                        Log.d(TAG, "TTS finished: $utteranceId")
                        callback.onSpeakingFinished()
                    }

                    @Deprecated("Deprecated in API level 21")
                    override fun onError(utteranceId: String?) {
                        Log.e(TAG, "TTS error: $utteranceId")
                    }

                    override fun onError(utteranceId: String?, errorCode: Int) {
                        Log.e(TAG, "TTS error: $utteranceId, code=$errorCode")
                    }
                })

                isTtsReady = true
                Log.i(TAG, "TTS initialized successfully")
            } else {
                Log.e(TAG, "TTS initialization failed with status: $status")
            }
        }
    }

    /**
     * Initializes the SpeechRecognizer for STT.
     */
    private fun initStt() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.e(TAG, "Speech recognition not available on this device")
            callback.onSpeechError("Speech recognition not available")
            return
        }
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
        speechRecognizer?.setRecognitionListener(recognitionListener)
        Log.i(TAG, "STT initialized successfully")
    }

    /**
     * Initializes the tone generator for the "ready to listen" beep.
     */
    private fun initToneGenerator() {
        try {
            toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
        } catch (e: Exception) {
            Log.w(TAG, "Could not create ToneGenerator: ${e.message}")
        }
    }

    // ── Public API: TTS ─────────────────────────────────────────────

    /**
     * Speaks the given text using TTS. If [flush] is true, interrupts any
     * currently-speaking utterance. Otherwise, queues behind current speech.
     *
     * @param text The text to speak.
     * @param flush If true, interrupts current speech. If false, queues.
     */
    fun speak(text: String, flush: Boolean = true) {
        if (!isTtsReady) {
            Log.w(TAG, "TTS not ready, cannot speak: $text")
            return
        }
        val queueMode = if (flush) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
        val utteranceId = UUID.randomUUID().toString()
        val params = Bundle().apply {
            putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId)
        }
        tts?.speak(text, queueMode, params, utteranceId)
        Log.i(TAG, "Speaking (flush=$flush): $text")
    }

    /**
     * Stops any current TTS speech immediately.
     */
    fun stopSpeaking() {
        tts?.stop()
    }

    /**
     * Returns true if TTS is currently speaking.
     */
    fun isSpeaking(): Boolean = tts?.isSpeaking == true

    // ── Public API: STT ─────────────────────────────────────────────

    /**
     * Starts listening for voice input.
     * Stops any current TTS first to prevent feedback.
     * Plays a beep to indicate the mic is active.
     */
    fun startListening() {
        if (isListening) {
            Log.w(TAG, "Already listening, ignoring startListening()")
            return
        }

        // Stop TTS to avoid feedback loop
        stopSpeaking()

        // Play a beep to signal the user that the mic is active
        playBeep()

        // Build the STT intent
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            // Shorter silence timeout — user is giving brief voice commands
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1000L)
            putExtra(
                RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS,
                1500L
            )
        }

        try {
            speechRecognizer?.startListening(intent)
            isListening = true
            Log.i(TAG, "STT listening started")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start STT: ${e.message}")
            callback.onSpeechError("Could not start voice recognition")
        }
    }

    /**
     * Stops the current STT listening session.
     */
    fun stopListening() {
        if (isListening) {
            speechRecognizer?.stopListening()
            isListening = false
            Log.i(TAG, "STT listening stopped")
        }
    }

    // ── RecognitionListener ─────────────────────────────────────────

    private val recognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "STT ready for speech")
            callback.onListeningStarted()
        }

        override fun onBeginningOfSpeech() {
            Log.d(TAG, "STT detected beginning of speech")
        }

        override fun onRmsChanged(rmsdB: Float) {
            // Could visualize audio level — not needed for blind users
        }

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.d(TAG, "STT detected end of speech")
            isListening = false
            callback.onListeningStopped()
        }

        override fun onError(error: Int) {
            isListening = false
            callback.onListeningStopped()
            val errorMsg = when (error) {
                SpeechRecognizer.ERROR_AUDIO -> "Audio recording error"
                SpeechRecognizer.ERROR_CLIENT -> "Client side error"
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission denied"
                SpeechRecognizer.ERROR_NETWORK -> "Network error"
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout"
                SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognition service busy"
                SpeechRecognizer.ERROR_SERVER -> "Server error"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech heard"
                else -> "Unknown error ($error)"
            }
            Log.e(TAG, "STT error: $errorMsg")
            // ERROR_NO_MATCH and SPEECH_TIMEOUT are normal — user just didn't speak
            if (error != SpeechRecognizer.ERROR_NO_MATCH &&
                error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT
            ) {
                callback.onSpeechError(errorMsg)
            } else {
                callback.onSpeechError("I didn't hear anything. Tap the button to try again.")
            }
        }

        override fun onResults(results: Bundle?) {
            isListening = false
            callback.onListeningStopped()
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val bestResult = matches?.firstOrNull()?.trim()
            if (!bestResult.isNullOrEmpty()) {
                Log.i(TAG, "STT result: $bestResult")
                callback.onSpeechResult(bestResult)
            } else {
                callback.onSpeechError("I didn't catch that. Please try again.")
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val partial = matches?.firstOrNull()?.trim()
            if (!partial.isNullOrEmpty()) {
                callback.onPartialResult(partial)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    // ── Beep ────────────────────────────────────────────────────────

    /**
     * Plays a short beep to indicate the mic is now active.
     * Uses ToneGenerator for a quick, non-blocking tone.
     */
    private fun playBeep() {
        try {
            toneGenerator?.startTone(ToneGenerator.TONE_PROP_BEEP, 150)
        } catch (e: Exception) {
            Log.w(TAG, "Could not play beep: ${e.message}")
        }
    }

    // ── Cleanup ─────────────────────────────────────────────────────

    /**
     * Releases all voice resources. Call in onDestroy.
     */
    fun shutdown() {
        speechRecognizer?.destroy()
        speechRecognizer = null
        tts?.stop()
        tts?.shutdown()
        tts = null
        toneGenerator?.release()
        toneGenerator = null
        Log.i(TAG, "VoiceHelper shut down")
    }
}
