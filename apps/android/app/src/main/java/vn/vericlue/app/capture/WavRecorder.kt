package vn.vericlue.app.capture

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.sqrt
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
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

/** Native microphone boundary; JVM tests exercise the recording lifecycle without Android audio. */
internal interface PcmInput {
    val bufferSize: Int
    val recording: Boolean
    fun start()
    fun read(buffer: ByteArray): Int
    fun stop()
    fun release()
}

enum class AudioCaptureState { Idle, Recording, Completed, Failed }

enum class VoiceCapturePhase { Idle, Preparing, Recording, Finished, Failed }
enum class VoiceCaptureFailure { Camera, Audio }

/** Coordinates camera preparation, microphone readiness, and one submission per attempt. */
class VoiceCapture(
    private val scope: CoroutineScope,
    private val prepareVideo: suspend () -> Boolean,
    private val startAudio: () -> Boolean,
    private val stopAudio: () -> ByteArray,
    private val stopVideo: () -> Unit,
    private val onFinished: (ByteArray) -> Unit,
    private val onFailure: (VoiceCaptureFailure) -> Unit,
    private val onAudioReady: () -> Boolean = { true },
) {
    private val _phase = MutableStateFlow(VoiceCapturePhase.Idle)
    val phase: StateFlow<VoiceCapturePhase> = _phase
    private var preparing: Job? = null
    private var generation = 0

    fun start() {
        if (_phase.value != VoiceCapturePhase.Idle || !scope.isActive) return
        _phase.value = VoiceCapturePhase.Preparing
        val attempt = ++generation
        preparing = scope.launch(start = CoroutineStart.LAZY) {
            var failure = VoiceCaptureFailure.Camera
            try {
                val videoReady = prepareVideo()
                currentCoroutineContext().ensureActive()
                if (attempt != generation) return@launch
                if (!videoReady) { fail(failure); return@launch }
                failure = VoiceCaptureFailure.Audio
                if (!startAudio()) { fail(failure); return@launch }
                failure = VoiceCaptureFailure.Camera
                if (!onAudioReady()) { fail(failure); return@launch }
                _phase.value = VoiceCapturePhase.Recording
            } catch (cancelled: CancellationException) {
                if (attempt == generation) cancel()
                throw cancelled
            } catch (_: Exception) {
                if (attempt == generation) fail(failure)
            }
        }
        preparing?.start()
    }

    fun finish() {
        if (_phase.value == VoiceCapturePhase.Preparing) { cancel(); return }
        if (_phase.value != VoiceCapturePhase.Recording) return
        _phase.value = VoiceCapturePhase.Finished
        val wav = cleanUp()
        if (wav.isEmpty()) {
            _phase.value = VoiceCapturePhase.Failed
            onFailure(VoiceCaptureFailure.Audio)
        } else onFinished(wav)
    }

    fun fail(failure: VoiceCaptureFailure) {
        if (_phase.value !in setOf(VoiceCapturePhase.Preparing, VoiceCapturePhase.Recording)) return
        _phase.value = VoiceCapturePhase.Failed
        cleanUp()
        onFailure(failure)
    }

    fun cancel() {
        if (_phase.value !in setOf(VoiceCapturePhase.Preparing, VoiceCapturePhase.Recording)) return
        _phase.value = VoiceCapturePhase.Idle
        cleanUp()
    }

    private fun cleanUp(): ByteArray {
        generation++
        preparing?.cancel()
        preparing = null
        val wav = runCatching { stopAudio() }.getOrDefault(ByteArray(0))
        runCatching { stopVideo() }
        return wav
    }
}

@SuppressLint("MissingPermission")
private fun openPcmInput(): PcmInput? {
    val minBuf = AudioRecord.getMinBufferSize(Wav.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
    if (minBuf <= 0) return null
    val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, Wav.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
    if (rec.state != AudioRecord.STATE_INITIALIZED) {
        rec.release()
        return null
    }
    return object : PcmInput {
        override val bufferSize = minBuf
        override val recording get() = rec.recordingState == AudioRecord.RECORDSTATE_RECORDING
        override fun start() = rec.startRecording()
        override fun read(buffer: ByteArray) = rec.read(buffer, 0, buffer.size)
        override fun stop() = rec.stop()
        override fun release() = rec.release()
    }
}

/** Records mono 16 kHz PCM WAV, up to [maxMs]; [level] drives the waveform. */
class WavRecorder internal constructor(
    private val maxMs: Int = 8_000,
    private val inputFactory: () -> PcmInput? = ::openPcmInput,
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) {
    private val _level = MutableStateFlow(0f)
    val level: StateFlow<Float> = _level
    private val _state = MutableStateFlow(AudioCaptureState.Idle)
    val state: StateFlow<AudioCaptureState> = _state

    private class Recording(val input: PcmInput) {
        val pcm = ByteArrayOutputStream()
        var job: Job? = null
        var accepting = true
        private val closed = AtomicBoolean(false)

        fun close() {
            if (closed.compareAndSet(false, true)) {
                runCatching { input.stop() }
                runCatching { input.release() }
            }
        }
    }

    private val lock = Any()
    private var recording: Recording? = null

    @SuppressLint("MissingPermission") // permission is requested on the permission screen
    fun start(scope: CoroutineScope): Boolean = synchronized(lock) {
        recording?.let { return _state.value == AudioCaptureState.Recording }
        if (!scope.isActive) return false
        val rec = runCatching { inputFactory() }.getOrNull() ?: run {
            _state.value = AudioCaptureState.Failed
            return false
        }
        val take = Recording(rec)
        if (!runCatching { rec.start(); rec.recording }.getOrDefault(false)) {
            take.close()
            _state.value = AudioCaptureState.Failed
            return false
        }
        recording = take
        _state.value = AudioCaptureState.Recording
        val maxBytes = Wav.SAMPLE_RATE * 2 * maxMs / 1000
        take.job = scope.launch(dispatcher) {
            try {
                val buf = ByteArray(rec.bufferSize)
                while (isActive) {
                    val n = rec.read(buf)
                    synchronized(lock) {
                        // A blocking native read can return after Stop or a new attempt.
                        if (recording !== take || !take.accepting) return@launch
                        check(n > 0) { "Microphone read failed" }
                        val written = minOf(n, maxBytes - take.pcm.size())
                        take.pcm.write(buf, 0, written)
                        _level.value = rms(buf, written)
                        if (take.pcm.size() >= maxBytes) {
                            take.accepting = false
                            take.close()
                            _level.value = 0f
                            _state.value = AudioCaptureState.Completed
                            return@launch
                        }
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                synchronized(lock) {
                    if (recording === take && take.accepting) {
                        take.accepting = false
                        _level.value = 0f
                        _state.value = AudioCaptureState.Failed
                    }
                }
            } finally {
                take.close()
            }
        }
        take.job?.invokeOnCompletion {
            take.close()
            synchronized(lock) {
                if (recording === take && take.accepting) {
                    take.accepting = false
                    _level.value = 0f
                    _state.value = AudioCaptureState.Failed
                }
            }
        }
        true
    }

    /** Stops and returns the WAV bytes (empty when nothing was recorded). */
    fun stop(): ByteArray {
        val take = synchronized(lock) {
            val previous = recording
            previous?.accepting = false
            recording = null
            _level.value = 0f
            _state.value = AudioCaptureState.Idle
            previous
        }
        take?.job?.cancel()
        // Stop unblocks a pending native read; it cannot append after accepting was cleared.
        take?.close()
        val pcm = synchronized(lock) { take?.pcm?.toByteArray() ?: ByteArray(0) }
        return if (pcm.isEmpty()) pcm else Wav.encode(pcm)
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
