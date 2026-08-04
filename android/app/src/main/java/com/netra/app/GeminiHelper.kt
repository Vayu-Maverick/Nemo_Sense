package com.netra.app

import android.util.Log
import com.google.ai.client.generativeai.GenerativeModel
import com.google.ai.client.generativeai.type.content
import com.google.ai.client.generativeai.type.generationConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * GeminiHelper — Interfaces with the Google Gemini API for natural language
 * understanding of voice commands from blind users.
 *
 * Responsibilities:
 *   1. Parse user speech into an intent (navigate, stop, resume, query, speed_change)
 *   2. Extract destination names for geocoding
 *   3. Generate natural, concise TTS responses (≤2 sentences)
 *
 * The system prompt instructs Gemini to act as "Netra", a guide dog rover
 * assistant. It responds in a structured format so we can parse both the
 * intent/action and the spoken response.
 *
 * ============================================================
 * API KEY SETUP:
 *   Get your key at: https://aistudio.google.com/app/apikey
 *   Place it in app/build.gradle.kts as:
 *     buildConfigField("String", "GEMINI_API_KEY", "\"your-key-here\"")
 *   Or in res/values/strings.xml as:
 *     <string name="gemini_api_key">your-key-here</string>
 * ============================================================
 */
class GeminiHelper(apiKey: String) {

    companion object {
        private const val TAG = "NetraGemini"

        /**
         * System prompt that defines Netra's personality and output format.
         *
         * The structured output format (ACTION: / DESTINATION: / RESPONSE:)
         * allows reliable parsing without requiring Gemini's structured output
         * mode, which isn't always available on all model versions.
         */
        private const val SYSTEM_PROMPT = """You are Netra, a guide dog rover assistant for blind users. You help with navigation.

When the user says a destination, extract it and respond with a brief confirmation.
Respond concisely — the user cannot read, only hear.
If the user says 'stop', 'slow down', 'speed up', 'what's around me', etc., respond naturally.
Always confirm the destination before starting navigation.
Keep responses under 2 sentences.

You MUST respond in EXACTLY this format (each field on its own line):
ACTION: <one of: navigate|stop|resume|query|speed_up|speed_down|status>
DESTINATION: <extracted destination name, or NONE if not applicable>
RESPONSE: <your natural spoken response to the user>

Examples:
User: "Take me to Vijay Cross Roads"
ACTION: navigate
DESTINATION: Vijay Cross Roads
RESPONSE: Navigating to Vijay Cross Roads. Hold on, calculating your route.

User: "Stop"
ACTION: stop
DESTINATION: NONE
RESPONSE: Stopping the rover now.

User: "What's around me?"
ACTION: query
DESTINATION: NONE
RESPONSE: Let me check the surroundings for you.

User: "Go faster"
ACTION: speed_up
DESTINATION: NONE
RESPONSE: Increasing speed.

User: "Slow down"
ACTION: speed_down
DESTINATION: NONE
RESPONSE: Slowing down for you."""
    }

    /**
     * Data class representing the parsed result from Gemini.
     *
     * @property action The parsed intent action.
     * @property destination The extracted destination name, or null if none.
     * @property response The natural language response to speak via TTS.
     */
    data class GeminiResult(
        val action: String,       // navigate, stop, resume, query, speed_up, speed_down, status
        val destination: String?, // e.g., "Vijay Cross Roads" or null
        val response: String      // Natural language response for TTS
    )

    // ── Generative Model ────────────────────────────────────────────

    private val model = GenerativeModel(
        modelName = "gemini-2.0-flash",
        apiKey = apiKey,
        generationConfig = generationConfig {
            temperature = 0.3f        // Low temperature for deterministic parsing
            topK = 20
            topP = 0.8f
            maxOutputTokens = 256     // Short responses only
        },
        systemInstruction = content { text(SYSTEM_PROMPT) }
    )

    // Use a chat session to maintain conversation context
    // (e.g., user says "take me there" after discussing a place)
    private val chat = model.startChat()

    // ── Public API ──────────────────────────────────────────────────

    /**
     * Sends the user's speech text to Gemini and parses the structured response.
     *
     * @param userText The transcribed speech from the user.
     * @return [GeminiResult] with action, destination, and spoken response.
     *         Returns a fallback result on any error.
     */
    suspend fun processCommand(userText: String): GeminiResult = withContext(Dispatchers.IO) {
        try {
            Log.i(TAG, "Processing command: \"$userText\"")

            val response = chat.sendMessage(userText)
            val responseText = response.text?.trim() ?: ""

            Log.d(TAG, "Gemini raw response:\n$responseText")

            // Parse the structured response
            parseStructuredResponse(responseText)

        } catch (e: Exception) {
            Log.e(TAG, "Gemini API error: ${e.message}", e)
            // Return a graceful fallback so the user still gets feedback
            GeminiResult(
                action = "query",
                destination = null,
                response = "I'm having trouble understanding right now. Please try again."
            )
        }
    }

    // ── Response parsing ────────────────────────────────────────────

    /**
     * Parses the structured ACTION/DESTINATION/RESPONSE format from Gemini.
     *
     * Falls back to treating the entire response as a "query" action if
     * the format isn't recognized (defensive parsing).
     */
    private fun parseStructuredResponse(text: String): GeminiResult {
        var action = "query"
        var destination: String? = null
        var response = text // Default: use full text as response

        // Parse each line looking for our structured fields
        val lines = text.lines()
        for (line in lines) {
            val trimmed = line.trim()
            when {
                trimmed.startsWith("ACTION:", ignoreCase = true) -> {
                    action = trimmed.substringAfter(":").trim().lowercase()
                }
                trimmed.startsWith("DESTINATION:", ignoreCase = true) -> {
                    val dest = trimmed.substringAfter(":").trim()
                    destination = if (dest.equals("NONE", ignoreCase = true) || dest.isEmpty()) {
                        null
                    } else {
                        dest
                    }
                }
                trimmed.startsWith("RESPONSE:", ignoreCase = true) -> {
                    response = trimmed.substringAfter(":").trim()
                }
            }
        }

        // Validate action is one of our known types
        val validActions = setOf("navigate", "stop", "resume", "query", "speed_up", "speed_down", "status")
        if (action !in validActions) {
            Log.w(TAG, "Unknown action '$action', defaulting to 'query'")
            action = "query"
        }

        val result = GeminiResult(action, destination, response)
        Log.i(TAG, "Parsed: action=$action, destination=$destination, response=$response")
        return result
    }
}
