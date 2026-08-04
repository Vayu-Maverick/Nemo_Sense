package com.example.guidesense

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.Locale

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private var speechRecognizer: SpeechRecognizer? = null
    
    // UI States
    private var statusText by mutableStateOf("Ready to Guide")
    private var isListening by mutableStateOf(false)
    private var spokenText by mutableStateOf("")

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        if (permissions.all { it.value }) {
            setupSpeech()
        } else {
            statusText = "Permissions Required!"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        tts = TextToSpeech(this, this)
        
        permissionLauncher.launch(arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.BLUETOOTH_SCAN
        ))

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color.Black // High contrast background
                ) {
                    GuideSenseUI(
                        statusText = statusText,
                        spokenText = spokenText,
                        isListening = isListening,
                        onMicTap = { toggleListening() }
                    )
                }
            }
        }
    }

    private fun setupSpeech() {
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) { isListening = true; statusText = "Listening..." }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { isListening = false; statusText = "Processing..." }
                override fun onError(error: Int) { 
                    isListening = false
                    statusText = "Error listening. Tap again."
                }
                override fun onResults(results: Bundle?) {
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        val text = matches[0]
                        spokenText = text
                        processCommand(text)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        } else {
            statusText = "Speech Recognition not available."
        }
    }

    private fun toggleListening() {
        if (isListening) {
            speechRecognizer?.stopListening()
            isListening = false
        } else {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            }
            speechRecognizer?.startListening(intent)
        }
    }

    private fun processCommand(command: String) {
        // Send command to Gemini API (Mocked here for quick compile)
        // Send via BT SPP to Q
        val response = "Navigating to $command. Connecting to rover."
        statusText = "Routing..."
        speak(response)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
            speak("Netra Guide Sense is ready. Tap the screen to speak.")
        }
    }

    private fun speak(text: String) {
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "")
        statusText = text
    }

    override fun onDestroy() {
        super.onDestroy()
        tts.stop()
        tts.shutdown()
        speechRecognizer?.destroy()
    }
}

@Composable
fun GuideSenseUI(
    statusText: String,
    spokenText: String,
    isListening: Boolean,
    onMicTap: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = "NETRA",
            fontSize = 42.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        
        Text(
            text = statusText,
            fontSize = 32.sp,
            color = Color.Yellow,
            modifier = Modifier.padding(vertical = 16.dp)
        )
        
        if (spokenText.isNotEmpty()) {
            Text(
                text = "You said: $spokenText",
                fontSize = 24.sp,
                color = Color.LightGray
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = onMicTap,
            modifier = Modifier
                .fillMaxWidth()
                .height(300.dp), // HUGE button for blind users
            shape = CircleShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = if (isListening) Color.Red else Color(0xFF00AA00)
            )
        ) {
            Text(
                text = if (isListening) "STOP" else "TAP TO SPEAK",
                fontSize = 48.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }
    }
}
