package com.netra.app

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * RouteHelper — Handles geocoding and walking route calculation for navigation.
 *
 * Uses two free, no-API-key-required services:
 *   1. Nominatim (OpenStreetMap) — Geocodes place names to lat/lng coordinates
 *   2. OSRM (Open Source Routing Machine) — Calculates walking routes with
 *      turn-by-turn instructions
 *
 * All network calls run on the IO dispatcher (coroutines).
 */
class RouteHelper {

    companion object {
        private const val TAG = "NetraRoute"

        /** Nominatim geocoding API endpoint. Free, no key required. */
        private const val NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

        /** OSRM walking route API endpoint. Free, no key required. */
        private const val OSRM_URL = "http://router.project-osrm.org/route/v1/foot"

        /**
         * User-Agent header required by Nominatim's usage policy.
         * Must identify the app; generic user agents are blocked.
         */
        private const val USER_AGENT = "NetraGuideApp/1.0 (blind-navigation-rover)"
    }

    /**
     * Data class representing a geocoded location.
     */
    data class GeocodedLocation(
        val lat: Double,
        val lng: Double,
        val displayName: String
    )

    /**
     * Data class representing a waypoint along a route.
     */
    data class Waypoint(
        val lat: Double,
        val lng: Double
    )

    /**
     * Data class representing a complete walking route.
     */
    data class Route(
        /** Ordered list of waypoints along the route. */
        val waypoints: List<Waypoint>,
        /** Turn-by-turn text instructions (e.g., "Turn right on MG Road"). */
        val instructions: List<String>,
        /** Total distance in meters. */
        val distanceMeters: Double,
        /** Estimated duration in seconds. */
        val durationSeconds: Double
    )

    // ── HTTP Client ─────────────────────────────────────────────────

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    // ── Geocoding ───────────────────────────────────────────────────

    /**
     * Geocodes a place name to geographic coordinates using Nominatim.
     *
     * @param placeName The place name or address to geocode (e.g., "Vijay Cross Roads, Ahmedabad").
     * @return [GeocodedLocation] with lat/lng and display name, or null if not found.
     */
    suspend fun geocode(placeName: String): GeocodedLocation? = withContext(Dispatchers.IO) {
        try {
            val encodedQuery = java.net.URLEncoder.encode(placeName, "UTF-8")
            val url = "$NOMINATIM_URL?q=$encodedQuery&format=json&limit=1"

            Log.i(TAG, "Geocoding: $placeName → $url")

            val request = Request.Builder()
                .url(url)
                .header("User-Agent", USER_AGENT) // Required by Nominatim TOS
                .get()
                .build()

            val response = httpClient.newCall(request).execute()
            val body = response.body?.string()

            if (!response.isSuccessful || body.isNullOrEmpty()) {
                Log.e(TAG, "Geocoding failed: HTTP ${response.code}")
                return@withContext null
            }

            val results = JSONArray(body)
            if (results.length() == 0) {
                Log.w(TAG, "Geocoding: no results for '$placeName'")
                return@withContext null
            }

            val first = results.getJSONObject(0)
            val location = GeocodedLocation(
                lat = first.getDouble("lat"),
                lng = first.getDouble("lon"),
                displayName = first.getString("display_name")
            )

            Log.i(TAG, "Geocoded '$placeName' → ${location.lat}, ${location.lng}")
            location

        } catch (e: Exception) {
            Log.e(TAG, "Geocoding exception: ${e.message}", e)
            null
        }
    }

    // ── Routing ─────────────────────────────────────────────────────

    /**
     * Calculates a walking route between two points using OSRM.
     *
     * @param fromLat Starting latitude.
     * @param fromLng Starting longitude.
     * @param toLat Destination latitude.
     * @param toLng Destination longitude.
     * @return [Route] with waypoints and instructions, or null on failure.
     */
    suspend fun getWalkingRoute(
        fromLat: Double,
        fromLng: Double,
        toLat: Double,
        toLng: Double
    ): Route? = withContext(Dispatchers.IO) {
        try {
            // OSRM expects coordinates as lng,lat (note the order!)
            val url = "$OSRM_URL/$fromLng,$fromLat;$toLng,$toLat" +
                    "?steps=true&overview=full&geometries=geojson"

            Log.i(TAG, "Routing: ($fromLat,$fromLng) → ($toLat,$toLng)")

            val request = Request.Builder()
                .url(url)
                .header("User-Agent", USER_AGENT)
                .get()
                .build()

            val response = httpClient.newCall(request).execute()
            val body = response.body?.string()

            if (!response.isSuccessful || body.isNullOrEmpty()) {
                Log.e(TAG, "Routing failed: HTTP ${response.code}")
                return@withContext null
            }

            val json = JSONObject(body)
            val code = json.getString("code")
            if (code != "Ok") {
                Log.e(TAG, "OSRM error: $code")
                return@withContext null
            }

            val routes = json.getJSONArray("routes")
            if (routes.length() == 0) {
                Log.w(TAG, "No routes found")
                return@withContext null
            }

            val routeObj = routes.getJSONObject(0)
            val distance = routeObj.getDouble("distance")
            val duration = routeObj.getDouble("duration")

            // Extract waypoints from the geometry
            val geometry = routeObj.getJSONObject("geometry")
            val coordinates = geometry.getJSONArray("coordinates")
            val waypoints = mutableListOf<Waypoint>()
            for (i in 0 until coordinates.length()) {
                val coord = coordinates.getJSONArray(i)
                // GeoJSON is [lng, lat]
                waypoints.add(Waypoint(lat = coord.getDouble(1), lng = coord.getDouble(0)))
            }

            // Extract turn-by-turn instructions from steps
            val instructions = mutableListOf<String>()
            val legs = routeObj.getJSONArray("legs")
            for (legIdx in 0 until legs.length()) {
                val leg = legs.getJSONObject(legIdx)
                val steps = leg.getJSONArray("steps")
                for (stepIdx in 0 until steps.length()) {
                    val step = steps.getJSONObject(stepIdx)
                    val maneuver = step.getJSONObject("maneuver")
                    val instruction = buildInstructionFromStep(step, maneuver)
                    if (instruction.isNotEmpty()) {
                        instructions.add(instruction)
                    }
                }
            }

            val route = Route(
                waypoints = waypoints,
                instructions = instructions,
                distanceMeters = distance,
                durationSeconds = duration
            )

            Log.i(TAG, "Route found: ${waypoints.size} waypoints, " +
                    "${instructions.size} instructions, " +
                    "${distance.toInt()}m, ${(duration / 60).toInt()}min")

            route

        } catch (e: Exception) {
            Log.e(TAG, "Routing exception: ${e.message}", e)
            null
        }
    }

    // ── Instruction builder ─────────────────────────────────────────

    /**
     * Builds a human-readable instruction string from an OSRM step.
     *
     * OSRM provides maneuver type and modifier; we convert these into
     * blind-friendly spoken instructions (e.g., "Turn right on MG Road").
     */
    private fun buildInstructionFromStep(step: JSONObject, maneuver: JSONObject): String {
        val type = maneuver.optString("type", "")
        val modifier = maneuver.optString("modifier", "")
        val name = step.optString("name", "")
        val distance = step.optDouble("distance", 0.0).toInt()

        val action = when (type) {
            "depart" -> "Head ${modifier.ifEmpty { "forward" }}"
            "arrive" -> "Arrive at your destination"
            "turn" -> "Turn $modifier"
            "continue" -> "Continue $modifier"
            "new name" -> "Continue onto"
            "merge" -> "Merge $modifier"
            "fork" -> "Take the $modifier fork"
            "roundabout" -> "Enter the roundabout and take the $modifier exit"
            "rotary" -> "Enter the rotary and take the $modifier exit"
            "end of road" -> "At the end of the road, turn $modifier"
            else -> if (modifier.isNotEmpty()) modifier.replaceFirstChar { it.uppercase() } else ""
        }

        return when {
            action.isEmpty() -> ""
            name.isNotEmpty() && distance > 0 ->
                "$action on $name for $distance meters"
            name.isNotEmpty() ->
                "$action on $name"
            distance > 0 ->
                "$action for $distance meters"
            else -> action
        }
    }
}
