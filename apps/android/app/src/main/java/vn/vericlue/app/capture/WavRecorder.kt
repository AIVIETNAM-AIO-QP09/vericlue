package vn.vericlue.app.capture

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sqrt
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** WAV container for 16-bit PCM (same layout as apps/web/src/lib/capture/wav.ts). */
object Wav {
    const val SAMPLE_RATE = 16_000

    fun encode(pcm: ByteArray, sampleRate: Int = SAMPLE_RATE, channels: Int = 1): ByteArray {
        val byteRate = sampleRate * channels * 2
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray()); putInt(36 + pcm.size); put("WAVE".toByteArray())
            put("fmt ".toByteArray()); putInt(16); putShort(1); putShort(channels.toShort())
            putInt(sampleRate); putInt(byteRate); putShort((channels * 2).toShort()); putShort(16)
            put("data".toByteArray()); putInt(pcm.size)
        }
        return header.array() + pcm
    }
}

/**
 * Records the read-a-sentence answer: AudioRecord, PCM 16-bit, mono, 16 kHz, at most [maxMs] (APP-03).
 * [level] (0..1) drives the waveform on the voice screen.
 */
class WavRecorder(private val maxMs: Int = 8_000) {
    private val _level = MutableStateFlow(0f)
    val level: StateFlow<Float> = _level

    private var record: AudioRecord? = null
    private var job: Job? = null
    private val pcm = ByteArrayOutputStream()

    @SuppressLint("MissingPermission") // permission is requested on the permission screen
    fun start(scope: CoroutineScope): Boolean {
        if (job != null) return true
        val minBuf = AudioRecord.getMinBufferSize(Wav.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuf <= 0) return false
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, Wav.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            return false
        }
        pcm.reset()
        record = rec
        rec.startRecording()
        val maxBytes = Wav.SAMPLE_RATE * 2 * maxMs / 1000
        job = scope.launch(Dispatchers.IO) {
            val buf = ByteArray(minBuf)
            while (isActive && pcm.size() < maxBytes) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) continue
                pcm.write(buf, 0, minOf(n, maxBytes - pcm.size()))
                _level.value = rms(buf, n)
            }
        }
        return true
    }

    /** Stops and returns the WAV bytes (empty when nothing was recorded). */
    fun stop(): ByteArray {
        job?.cancel()
        job = null
        record?.run {
            runCatching { stop() }
            release()
        }
        record = null
        _level.value = 0f
        return if (pcm.size() == 0) ByteArray(0) else Wav.encode(pcm.toByteArray())
    }

    private fun rms(buf: ByteArray, n: Int): Float {
        var sum = 0.0
        var i = 0
        while (i + 1 < n) {
            val s = ((buf[i + 1].toInt() shl 8) or (buf[i].toInt() and 0xFF)).toShort().toDouble()
            sum += s * s
            i += 2
        }
        val samples = n / 2
        return if (samples == 0) 0f else (sqrt(sum / samples) / 8000.0).coerceIn(0.0, 1.0).toFloat()
    }
}
