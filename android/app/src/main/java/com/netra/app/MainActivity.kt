package com.netra.app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.util.Log
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.InputStream
import java.io.OutputStream
import java.util.Locale
import java.util.UUID

class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private lateinit var speechRecognizer: SpeechRecognizer
    private lateinit var btnSpeak: Button
    private lateinit var txtStatus: TextView

    // Bluetooth
    private val btAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()
    private var btSocket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null
    private var inputStream: InputStream? = null
    private val SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    
    // Gemini 
    // IMPORTANT: Replace this with your actual Gemini API Key
    private val generativeModel = GenerativeModel(
        modelName = "gemini-2.0-flash",
        apiKey = "YOUR_GEMINI_API_KEY",
        systemInstruction = com.google.ai.client.generativeai.type.content {
            text("You are GuideSense, a guide dog rover assistant for blind users. " +
                 "If the user says a destination, respond concisely confirming it and extract the intent as a JSON action. " +
                 "Output format: {\"response\": \"Confirming text\", \"action\": \"navigate\", \"destination\": \"destination_name\"}")
        }
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        btnSpeak = findViewById(R.id.btnSpeak)
        txtStatus = findViewById(R.id.txtStatus)

        // Initialize TTS
        tts = TextToSpeech(this, this)

        // Initialize STT
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onError(error: Int) {
                txtStatus.text = "Error listening. Tap again."
            }
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    val spokenText = matches[0]
                    txtStatus.text = "You said: $spokenText"
                    processWithGemini(spokenText)
                }
            }
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        btnSpeak.setOnClickListener {
            val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            speechRecognizer.startListening(intent)
            txtStatus.text = "Listening..."
        }

        // Connect to Rover
        connectToRover()
    }

    private fun connectToRover() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1)
            return
        }
        
        val pairedDevices: Set<BluetoothDevice>? = btAdapter?.bondedDevices
        val roverDevice = pairedDevices?.find { it.name == "NetraGuide" || it.name == "raspberrypi" } // Update name based on Q's BT name
        
        if (roverDevice != null) {
            try {
                btSocket = roverDevice.createRfcommSocketToServiceRecord(SPP_UUID)
                btSocket?.connect()
                outputStream = btSocket?.outputStream
                inputStream = btSocket?.inputStream
                txtStatus.text = "Connected to Rover"
                speakOut("Connected to rover.")
            } catch (e: Exception) {
                txtStatus.text = "Connection Failed"
            }
        } else {
            txtStatus.text = "Rover not paired."
        }
    }

    private fun processWithGemini(text: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = generativeModel.generateContent(text)
                val responseText = response.text ?: ""
                
                // Parse Gemini's JSON (assuming it returns JSON)
                try {
                    val json = JSONObject(responseText.replace("```json", "").replace("```", "").trim())
                    val reply = json.getString("response")
                    val action = json.getString("action")
                    
                    runOnUiThread {
                        speakOut(reply)
                        txtStatus.text = "Rover Action: $action"
                    }
                    
                    // Send command to rover
                    val cmd = JSONObject()
                    cmd.put("type", "command")
                    cmd.put("action", action)
                    if (json.has("destination")) {
                        cmd.put("destination", json.getString("destination"))
                    }
                    sendToRover(cmd.toString())
                    
                } catch (e: Exception) {
                    runOnUiThread { speakOut(responseText) }
                }
                
            } catch (e: Exception) {
                Log.e("GuideSense", "Gemini Error", e)
            }
        }
    }

    private fun sendToRover(data: String) {
        try {
            outputStream?.write((data + "\n").toByteArray())
        } catch (e: Exception) {
            Log.e("GuideSense", "BT Send Error", e)
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        tts.stop()
        tts.shutdown()
        btSocket?.close()
    }
}
