package com.netra.app

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Looper
import android.util.Log
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority

/**
 * LocationHelper — Provides GPS location updates using Google Play Services
 * Fused Location Provider.
 *
 * Streams the phone's location to the rover every ~1 second for real-time
 * navigation. The Fused Location Provider automatically selects the best
 * location source (GPS, Wi-Fi, cell) for optimal accuracy.
 *
 * Provides:
 *   • Latitude, longitude, accuracy
 *   • Speed (m/s) from GPS
 *   • Bearing/heading (degrees from north) from GPS movement
 */
class LocationHelper(context: Context) {

    companion object {
        private const val TAG = "NetraLocation"

        /** Location update interval in milliseconds (1 second for real-time nav). */
        private const val UPDATE_INTERVAL_MS = 1000L

        /** Fastest interval — won't receive updates faster than this even if available. */
        private const val FASTEST_INTERVAL_MS = 500L
    }

    /**
     * Callback for receiving location updates.
     */
    interface LocationCallback2 {
        /**
         * Called when a new location fix is available.
         * @param lat Latitude in degrees.
         * @param lng Longitude in degrees.
         * @param accuracy Estimated horizontal accuracy in meters.
         * @param speed Speed in m/s (0 if stationary or unavailable).
         * @param bearing Bearing in degrees (0–360, north-based). May be 0 if unavailable.
         */
        fun onLocationUpdate(lat: Double, lng: Double, accuracy: Float, speed: Float, bearing: Float)
    }

    // ── Internals ───────────────────────────────────────────────────

    private val fusedClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    private var callback: LocationCallback2? = null
    private var gmsCallback: LocationCallback? = null

    // Latest values accessible by getters (for building sensor JSON)
    @Volatile var latestLat: Double = 0.0; private set
    @Volatile var latestLng: Double = 0.0; private set
    @Volatile var latestAccuracy: Float = 0f; private set
    @Volatile var latestSpeed: Float = 0f; private set
    @Volatile var latestBearing: Float = 0f; private set
    @Volatile var hasLocation: Boolean = false; private set

    // ── Public API ──────────────────────────────────────────────────

    /**
     * Starts requesting location updates at 1-second intervals.
     *
     * Requires ACCESS_FINE_LOCATION permission to be granted before calling.
     * @param callback Callback for receiving location updates.
     */
    @SuppressLint("MissingPermission")
    fun startUpdates(callback: LocationCallback2) {
        this.callback = callback

        // Build high-accuracy location request
        val locationRequest = LocationRequest.Builder(
            Priority.PRIORITY_HIGH_ACCURACY,
            UPDATE_INTERVAL_MS
        ).apply {
            setMinUpdateIntervalMillis(FASTEST_INTERVAL_MS)
            setWaitForAccurateLocation(false) // Don't delay — rover needs continuous stream
        }.build()

        // Create GMS callback that dispatches to our callback
        gmsCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val location: Location = result.lastLocation ?: return
                updateFromLocation(location)
            }
        }

        // Start updates on main looper
        fusedClient.requestLocationUpdates(
            locationRequest,
            gmsCallback!!,
            Looper.getMainLooper()
        )

        Log.i(TAG, "Location updates started (interval=${UPDATE_INTERVAL_MS}ms)")

        // Also try to get the last known location immediately
        fetchLastKnownLocation()
    }

    /**
     * Stops location updates. Call in onPause or onDestroy to conserve battery.
     */
    fun stopUpdates() {
        gmsCallback?.let {
            fusedClient.removeLocationUpdates(it)
            Log.i(TAG, "Location updates stopped")
        }
        gmsCallback = null
    }

    // ── Internals ───────────────────────────────────────────────────

    /**
     * Attempts to get the last known location for a quick initial fix.
     */
    @SuppressLint("MissingPermission")
    private fun fetchLastKnownLocation() {
        fusedClient.lastLocation.addOnSuccessListener { location ->
            if (location != null) {
                updateFromLocation(location)
                Log.i(TAG, "Last known location: ${location.latitude}, ${location.longitude}")
            }
        }
    }

    /**
     * Updates internal state and notifies the callback with new location data.
     */
    private fun updateFromLocation(location: Location) {
        latestLat = location.latitude
        latestLng = location.longitude
        latestAccuracy = location.accuracy
        latestSpeed = if (location.hasSpeed()) location.speed else 0f
        latestBearing = if (location.hasBearing()) location.bearing else 0f
        hasLocation = true

        Log.d(TAG, "Location: $latestLat, $latestLng (±${latestAccuracy}m) " +
                "speed=${latestSpeed}m/s bearing=${latestBearing}°")

        callback?.onLocationUpdate(
            latestLat, latestLng, latestAccuracy, latestSpeed, latestBearing
        )
    }
}
