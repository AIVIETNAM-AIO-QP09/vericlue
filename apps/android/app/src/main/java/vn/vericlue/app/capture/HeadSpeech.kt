package vn.vericlue.app.capture

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener

/** Fixed guidance only; no recording/recognition or user data is sent to the speech engine. */
class HeadSpeech(
    context: Context,
    private val volume: Float = .45f,
    private val onReady: (Boolean) -> Unit = {},
    private val onFinished: (Boolean) -> Unit = {},
) : AutoCloseable {
    private val handler = Handler(Looper.getMainLooper())
    private var engine: TextToSpeech? = null
    private var tone: ToneGenerator? = null
    private var generation = 0L
    private var closed = false
    private var active = true
    private var available = false
    var networkRequired = false
        private set
    private var current: HeadCue? = null
    private var expiresAt = 0L
    private var fallbackToken: Long? = null
    private val scheduled = mutableListOf<Runnable>()

    private val appContext = context.applicationContext
    private val pendingEngines = mutableListOf<String>()
    private val triedEngines = mutableSetOf<String>()
    private val voiceSearch = HeadVoiceSearch()
    private var retryingNetwork = false
    private var connection = 0L
    private var connectionTimeout: Runnable? = null
    private var attempts = 0
    private val listener = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) { handler.post {
            if (!closed && utteranceId == generation.toString() && SystemClock.elapsedRealtime() >= expiresAt) stop()
        } }
        override fun onDone(utteranceId: String?) { handler.post {
            if (!closed && active && utteranceId == generation.toString()) onFinished(true)
        } }
        @Deprecated("Platform callback")
        override fun onError(utteranceId: String?) { handler.post {
            if (!closed && active && utteranceId == generation.toString() && SystemClock.elapsedRealtime() < expiresAt) {
                current?.let { fallback(it, generation) }
                onFinished(false)
            }
        } }
    }

    init { connect(null) }

    /** Try installed engines without changing the user's system-wide TTS preference. */
    private fun connect(packageName: String?) {
        if (closed) return
        val token = ++connection
        attempts++
        connectionTimeout?.let { handler.removeCallbacks(it) }
        packageName?.let { triedEngines.add(it) }
        var candidate: TextToSpeech? = null
        candidate = runCatching {
            TextToSpeech(appContext, { status -> handler.post {
                val tts = candidate ?: return@post
                if (closed || token != connection) { runCatching { tts.shutdown() }; return@post }
                connectionTimeout?.let { handler.removeCallbacks(it) }
                available = runCatching {
                    if (status != TextToSpeech.SUCCESS) return@runCatching false
                    val voices = tts.voices.orEmpty().filter {
                        it.locale.language in setOf("vi", "vie") &&
                            TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED !in it.features.orEmpty()
                    }.sortedWith(compareBy<android.speech.tts.Voice> { it.isNetworkConnectionRequired }
                        .thenByDescending { it.quality }
                        .thenBy { it.latency }.thenBy { it.name })
                    if (!voiceSearch.accept(packageName ?: tts.defaultEngine,
                        hasOffline = voices.any { !it.isNetworkConnectionRequired },
                        hasNetwork = voices.any { it.isNetworkConnectionRequired })) return@runCatching false
                    val voice = voices.firstOrNull() ?: return@runCatching false
                    networkRequired = voice.isNetworkConnectionRequired
                    tts.setVoice(voice) == TextToSpeech.SUCCESS
                }.getOrDefault(false)
                if (!available) { nextEngine(); return@post }
                runCatching {
                    tts.setSpeechRate(1f)
                    tts.setAudioAttributes(AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                }
                onReady(true)
            } }, packageName)
        }.getOrNull()
        engine = candidate
        runCatching {
            if (packageName == null) candidate?.defaultEngine?.let { triedEngines.add(it) }
            candidate?.engines.orEmpty().map { it.name }.filter { it !in triedEngines && it !in pendingEngines }
                .forEach { pendingEngines.add(it) }
            candidate?.setOnUtteranceProgressListener(listener)
        }
        if (candidate == null) { handler.post { if (!closed && token == connection) nextEngine() }; return }
        val timeout = Runnable { if (!closed && token == connection && !available) nextEngine() }
        connectionTimeout = timeout
        handler.postDelayed(timeout, 4000)
    }

    private fun nextEngine() {
        if (closed) return
        runCatching { engine?.shutdown() }
        val next = pendingEngines.firstOrNull { it !in triedEngines }
        if (!retryingNetwork && next != null && attempts < 4) { pendingEngines.remove(next); connect(next) }
        else {
            val fallback = voiceSearch.fallback()
            if (fallback != null) {
                retryingNetwork = true
                connect(fallback)
                return
            }
            connection++
            connectionTimeout?.let { handler.removeCallbacks(it) }
            available = false
            onReady(false)
        }
    }

    fun say(cue: HeadCue) {
        if (closed || !active) return
        stop()
        current = cue
        expiresAt = SystemClock.elapsedRealtime() + 2000L
        val params = Bundle().apply { putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, volume.coerceIn(0f, 1f)) }
        val accepted = available && runCatching {
            engine?.speak(cue.text, TextToSpeech.QUEUE_FLUSH, params, generation.toString()) == TextToSpeech.SUCCESS
        }.getOrDefault(false)
        // Critical stop/correction cues remain immediate even if a speech engine is slow.
        if (!accepted || cue == HeadCue.Hold || cue == HeadCue.Center || cue.warning) fallback(cue, generation)
    }

    private fun fallback(cue: HeadCue, token: Long) {
        if (closed || !active || token != generation || fallbackToken == token) return
        fallbackToken = token
        if (volume <= 0f) return // Silent device probe must never wake the user.
        if (tone == null) tone = runCatching { ToneGenerator(AudioManager.STREAM_NOTIFICATION, 25) }.getOrNull()
        var offset = 0L
        for (duration in cue.beeps) {
            val task = Runnable {
                if (!closed && active && generation == token) runCatching {
                    tone?.startTone(ToneGenerator.TONE_PROP_BEEP, duration.toInt())
                }
            }
            scheduled += task
            handler.postDelayed(task, offset)
            offset += duration + 90L
        }
    }

    fun stop() {
        generation++
        current = null
        scheduled.forEach { handler.removeCallbacks(it) }
        scheduled.clear()
        runCatching { engine?.stop() }
        runCatching { tone?.stopTone() }
    }
    fun pause() { active = false; stop() }
    fun resume() { if (!closed) active = true }
    override fun close() {
        if (closed) return
        closed = true
        connection++
        connectionTimeout?.let { handler.removeCallbacks(it) }
        stop()
        runCatching { engine?.shutdown() }
        runCatching { tone?.release() }
    }
}
