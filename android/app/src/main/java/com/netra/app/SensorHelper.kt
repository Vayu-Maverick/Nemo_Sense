package com.netra.app

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.util.Log

/**
 * SensorHelper — Provides smoothed accelerometer and magnetic field data.
 *
 * Used for:
 *   • Streaming accelerometer readings to the rover for motion awareness
 *   • Computing device heading (compass bearing) from accelerometer + magnetometer
 *
 * A low-pass filter is applied to smooth out sensor noise. The filter
 * uses exponential moving average with a configurable alpha value.
 */
class SensorHelper(context: Context) : SensorEventListener {

    companion object {
        private const val TAG = "NetraSensor"

        /**
         * Low-pass filter alpha coefficient.
         * Lower values = smoother but laggier; higher = more responsive but noisier.
         * 0.15 is a good balance for walking-pace motion.
         */
        private const val FILTER_ALPHA = 0.15f
    }

    /**
     * Callback for receiving sensor updates.
     */
    interface SensorCallback {
        /**
         * Called when new smoothed accelerometer data is available.
         * @param x Acceleration along X-axis (m/s²)
         * @param y Acceleration along Y-axis (m/s²)
         * @param z Acceleration along Z-axis (m/s²)
         */
        fun onAccelerometerUpdate(x: Float, y: Float, z: Float)

        /**
         * Called when a new heading (compass bearing) is calculated.
         * @param headingDegrees Heading in degrees (0=North, 90=East, 180=South, 270=West)
         */
        fun onHeadingUpdate(headingDegrees: Float)
    }

    // ── Internals ───────────────────────────────────────────────────

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)

    private var callback: SensorCallback? = null

    // Smoothed sensor values (low-pass filtered)
    private val accelValues = FloatArray(3) // x, y, z
    private val magnetValues = FloatArray(3) // x, y, z
    private var hasMagnetData = false

    // Rotation matrix and orientation for heading computation
    private val rotationMatrix = FloatArray(9)
    private val orientationAngles = FloatArray(3)

    // Latest smoothed readings (accessible by getter for streaming to rover)
    @Volatile var latestAccelX: Float = 0f; private set
    @Volatile var latestAccelY: Float = 0f; private set
    @Volatile var latestAccelZ: Float = 0f; private set
    @Volatile var latestHeading: Float = 0f; private set

    // ── Public API ──────────────────────────────────────────────────

    /**
     * Starts listening to accelerometer and magnetometer sensors.
     * @param callback Optional callback for real-time updates.
     */
    fun start(callback: SensorCallback? = null) {
        this.callback = callback

        // Register accelerometer — SENSOR_DELAY_GAME (~20ms) for smooth data
        accelerometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
            Log.i(TAG, "Accelerometer registered")
        } ?: Log.w(TAG, "Accelerometer not available!")

        // Register magnetometer for heading calculation
        magnetometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
            Log.i(TAG, "Magnetometer registered")
        } ?: Log.w(TAG, "Magnetometer not available — heading will use GPS bearing only")
    }

    /**
     * Stops listening to all sensors. Call this in onPause or onDestroy.
     */
    fun stop() {
        sensorManager.unregisterListener(this)
        Log.i(TAG, "Sensors unregistered")
    }

    // ── SensorEventListener ─────────────────────────────────────────

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                // Apply low-pass filter to smooth accelerometer data
                lowPassFilter(event.values, accelValues)
                latestAccelX = accelValues[0]
                latestAccelY = accelValues[1]
                latestAccelZ = accelValues[2]
                callback?.onAccelerometerUpdate(latestAccelX, latestAccelY, latestAccelZ)

                // Recompute heading if we have magnetometer data
                if (hasMagnetData) {
                    computeHeading()
                }
            }

            Sensor.TYPE_MAGNETIC_FIELD -> {
                lowPassFilter(event.values, magnetValues)
                hasMagnetData = true
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Not used but required by interface
        Log.d(TAG, "Sensor accuracy changed: ${sensor?.name} → $accuracy")
    }

    // ── Heading computation ─────────────────────────────────────────

    /**
     * Computes the device heading (azimuth) from the accelerometer and
     * magnetometer using Android's rotation matrix.
     *
     * The result is in degrees: 0=North, 90=East, 180=South, 270=West.
     */
    private fun computeHeading() {
        val success = SensorManager.getRotationMatrix(
            rotationMatrix, null, accelValues, magnetValues
        )
        if (success) {
            SensorManager.getOrientation(rotationMatrix, orientationAngles)
            // orientationAngles[0] is azimuth in radians (-π to π)
            var azimuthDegrees = Math.toDegrees(orientationAngles[0].toDouble()).toFloat()
            // Normalize to 0–360
            if (azimuthDegrees < 0) azimuthDegrees += 360f
            latestHeading = azimuthDegrees
            callback?.onHeadingUpdate(latestHeading)
        }
    }

    // ── Low-pass filter ─────────────────────────────────────────────

    /**
     * Applies exponential moving average low-pass filter.
     * output[i] = output[i] + alpha * (input[i] - output[i])
     *
     * This smooths out high-frequency noise while retaining the general trend.
     *
     * @param input Raw sensor values from the event.
     * @param output Accumulated filtered values (modified in-place).
     */
    private fun lowPassFilter(input: FloatArray, output: FloatArray) {
        for (i in input.indices) {
            output[i] = output[i] + FILTER_ALPHA * (input[i] - output[i])
        }
    }
}
