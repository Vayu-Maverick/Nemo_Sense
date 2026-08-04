package com.example.guidesense

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.util.Log
import java.io.IOException
import java.io.OutputStream
import java.util.UUID

class BluetoothManager {
    private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    private var socket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null

    @SuppressLint("MissingPermission")
    fun connectToDevice(adapter: BluetoothAdapter, deviceName: String = "NetraGuide") {
        Thread {
            try {
                val pairedDevices: Set<BluetoothDevice> = adapter.bondedDevices
                val targetDevice = pairedDevices.find { it.name == deviceName }
                if (targetDevice != null) {
                    socket = targetDevice.createRfcommSocketToServiceRecord(SPP_UUID)
                    socket?.connect()
                    outputStream = socket?.outputStream
                    Log.d("Bluetooth", "Connected to $deviceName")
                }
            } catch (e: IOException) {
                Log.e("Bluetooth", "Connection failed", e)
            }
        }.start()
    }

    fun sendJson(jsonString: String) {
        if (outputStream != null) {
            try {
                val data = "$jsonString\n".toByteArray()
                outputStream?.write(data)
                outputStream?.flush()
            } catch (e: IOException) {
                Log.e("Bluetooth", "Send failed", e)
            }
        }
    }
}
