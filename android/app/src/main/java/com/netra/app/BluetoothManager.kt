package com.netra.app

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.os.Handler
import android.os.Looper
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.io.OutputStream
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

/**
 * BluetoothManager — Handles Bluetooth Classic SPP connection to the Netra rover.
 *
 * Protocol: JSON objects delimited by newlines ('\n') over RFCOMM.
 * The rover's Bluetooth module should be paired and named "NetraGuide".
 *
 * Features:
 *   • Scans paired devices for the rover by name
 *   • Connects via RFCOMM with SPP UUID
 *   • Background reader thread parses incoming JSON lines
 *   • Thread-safe send() writes JSON + newline + flush
 *   • Auto-reconnect on disconnect with exponential backoff
 *   • Callbacks dispatched on the main thread
 */
class BluetoothManager(private val callback: BluetoothCallback) {

    companion object {
        private const val TAG = "NetraBT"

        /** Standard SPP (Serial Port Profile) UUID for RFCOMM connections. */
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        /** Name of the rover's Bluetooth module. Change if your HC-05/HC-06 has a different name. */
        private const val ROVER_NAME = "NetraGuide"

        /** Maximum number of auto-reconnect attempts before giving up. */
        private const val MAX_RECONNECT_ATTEMPTS = 5

        /** Base delay for exponential backoff reconnect (ms). */
        private const val RECONNECT_BASE_DELAY_MS = 2000L
    }

    /**
     * Callback interface for Bluetooth events.
     * All callbacks are invoked on the main (UI) thread.
     */
    interface BluetoothCallback {
        /** Called when RFCOMM connection is successfully established. */
        fun onConnected()

        /** Called when the connection is lost or explicitly disconnected. */
        fun onDisconnected()

        /** Called when a complete JSON message is received from the rover. */
        fun onMessageReceived(message: JSONObject)

        /** Called when a connection attempt fails. [attempt] is 1-based. */
        fun onConnectionFailed(attempt: Int, maxAttempts: Int)
    }

    // ── Internal state ──────────────────────────────────────────────

    private val bluetoothAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()
    private var socket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null
    private var readerThread: Thread? = null
    private val isConnected = AtomicBoolean(false)
    private val shouldReconnect = AtomicBoolean(true)
    private val mainHandler = Handler(Looper.getMainLooper())

    // ── Public API ──────────────────────────────────────────────────

    /**
     * Returns true if Bluetooth hardware is available on this device.
     */
    fun isBluetoothAvailable(): Boolean = bluetoothAdapter != null

    /**
     * Returns true if Bluetooth is currently enabled.
     */
    fun isBluetoothEnabled(): Boolean = bluetoothAdapter?.isEnabled == true

    /**
     * Returns true if the RFCOMM socket is currently connected.
     */
    fun isConnected(): Boolean = isConnected.get()

    /**
     * Initiates connection to the rover on a background thread.
     * Searches paired devices for one named [ROVER_NAME].
     * If found, connects via RFCOMM. If not, invokes [BluetoothCallback.onConnectionFailed].
     */
    @SuppressLint("MissingPermission")
    fun connect() {
        shouldReconnect.set(true)
        Thread { connectInternal(1) }.start()
    }

    /**
     * Disconnects from the rover and stops the reader thread.
     * Disables auto-reconnect.
     */
    fun disconnect() {
        shouldReconnect.set(false)
        closeSocket()
    }

    /**
     * Sends a JSON string to the rover over RFCOMM.
     * Appends a newline delimiter and flushes. Thread-safe.
     *
     * @param json The JSON string to send (without trailing newline).
     */
    @Synchronized
    fun send(json: String) {
        if (!isConnected.get()) {
            Log.w(TAG, "send() called while disconnected, ignoring: $json")
            return
        }
        try {
            outputStream?.let { stream ->
                stream.write((json + "\n").toByteArray(Charsets.UTF_8))
                stream.flush()
                Log.d(TAG, "Sent: $json")
            }
        } catch (e: IOException) {
            Log.e(TAG, "Send failed: ${e.message}")
            handleDisconnect()
        }
    }

    /**
     * Sends a JSONObject to the rover. Convenience overload.
     */
    fun send(jsonObject: JSONObject) {
        send(jsonObject.toString())
    }

    // ── Connection logic ────────────────────────────────────────────

    /**
     * Core connection logic. Runs on a background thread.
     * Searches paired devices, creates RFCOMM socket, connects,
     * and starts the reader thread.
     *
     * @param attempt Current reconnect attempt number (1-based).
     */
    @SuppressLint("MissingPermission")
    private fun connectInternal(attempt: Int) {
        if (attempt > MAX_RECONNECT_ATTEMPTS) {
            Log.e(TAG, "Max reconnect attempts reached ($MAX_RECONNECT_ATTEMPTS)")
            mainHandler.post { callback.onConnectionFailed(attempt, MAX_RECONNECT_ATTEMPTS) }
            return
        }

        Log.i(TAG, "Connection attempt $attempt/$MAX_RECONNECT_ATTEMPTS")

        // Step 1: Find the rover in paired devices
        val roverDevice = findRoverDevice()
        if (roverDevice == null) {
            Log.w(TAG, "Rover device '$ROVER_NAME' not found in paired devices")
            mainHandler.post { callback.onConnectionFailed(attempt, MAX_RECONNECT_ATTEMPTS) }
            // Retry with backoff
            if (shouldReconnect.get()) {
                val delay = RECONNECT_BASE_DELAY_MS * attempt
                Log.i(TAG, "Retrying in ${delay}ms...")
                Thread.sleep(delay)
                connectInternal(attempt + 1)
            }
            return
        }

        try {
            // Step 2: Create and connect RFCOMM socket
            Log.i(TAG, "Connecting to ${roverDevice.name} (${roverDevice.address})...")
            socket = roverDevice.createRfcommSocketToServiceRecord(SPP_UUID)
            socket?.connect()

            // Step 3: Get output stream for sending
            outputStream = socket?.outputStream

            // Step 4: Mark as connected and notify
            isConnected.set(true)
            Log.i(TAG, "Connected to ${roverDevice.name}")
            mainHandler.post { callback.onConnected() }

            // Step 5: Start background reader thread for incoming messages
            startReaderThread()

        } catch (e: IOException) {
            Log.e(TAG, "Connection failed on attempt $attempt: ${e.message}")
            closeSocket()
            mainHandler.post { callback.onConnectionFailed(attempt, MAX_RECONNECT_ATTEMPTS) }

            // Retry with exponential backoff
            if (shouldReconnect.get()) {
                val delay = RECONNECT_BASE_DELAY_MS * attempt
                Log.i(TAG, "Retrying in ${delay}ms...")
                Thread.sleep(delay)
                connectInternal(attempt + 1)
            }
        }
    }

    /**
     * Searches the list of paired Bluetooth devices for one named [ROVER_NAME].
     *
     * @return The [BluetoothDevice] if found, null otherwise.
     */
    @SuppressLint("MissingPermission")
    private fun findRoverDevice(): BluetoothDevice? {
        val pairedDevices = bluetoothAdapter?.bondedDevices ?: return null
        for (device in pairedDevices) {
            Log.d(TAG, "Paired device: ${device.name} (${device.address})")
            if (device.name == ROVER_NAME) {
                return device
            }
        }
        return null
    }

    // ── Reader thread ───────────────────────────────────────────────

    /**
     * Starts a background thread that reads newline-delimited JSON from the
     * rover's RFCOMM input stream. Each complete line is parsed as a JSONObject
     * and dispatched to the callback on the main thread.
     */
    private fun startReaderThread() {
        readerThread = Thread {
            Log.i(TAG, "Reader thread started")
            try {
                val reader = BufferedReader(
                    InputStreamReader(socket?.inputStream, Charsets.UTF_8)
                )
                var line: String?
                while (isConnected.get() && reader.readLine().also { line = it } != null) {
                    val trimmed = line?.trim() ?: continue
                    if (trimmed.isEmpty()) continue

                    Log.d(TAG, "Received: $trimmed")
                    try {
                        val json = JSONObject(trimmed)
                        mainHandler.post { callback.onMessageReceived(json) }
                    } catch (e: Exception) {
                        Log.w(TAG, "Failed to parse JSON: $trimmed", e)
                    }
                }
            } catch (e: IOException) {
                if (isConnected.get()) {
                    Log.e(TAG, "Reader thread IOException: ${e.message}")
                }
            } finally {
                Log.i(TAG, "Reader thread finished")
                handleDisconnect()
            }
        }.apply {
            name = "NetraBT-Reader"
            isDaemon = true
            start()
        }
    }

    // ── Disconnect handling ─────────────────────────────────────────

    /**
     * Handles an unexpected disconnect: closes socket, notifies callback,
     * and optionally triggers auto-reconnect.
     */
    private fun handleDisconnect() {
        if (!isConnected.getAndSet(false)) return // Already handled
        closeSocket()
        Log.i(TAG, "Disconnected from rover")
        mainHandler.post { callback.onDisconnected() }

        // Auto-reconnect if enabled
        if (shouldReconnect.get()) {
            Log.i(TAG, "Auto-reconnecting in ${RECONNECT_BASE_DELAY_MS}ms...")
            Thread {
                Thread.sleep(RECONNECT_BASE_DELAY_MS)
                if (shouldReconnect.get()) {
                    connectInternal(1)
                }
            }.start()
        }
    }

    /**
     * Safely closes the RFCOMM socket and nullifies references.
     */
    private fun closeSocket() {
        isConnected.set(false)
        try {
            outputStream?.close()
        } catch (_: IOException) {}
        try {
            socket?.close()
        } catch (_: IOException) {}
        outputStream = null
        socket = null
    }
}
