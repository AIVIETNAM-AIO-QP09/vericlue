package vn.vericlue.app.capture

import java.io.File
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import vn.vericlue.app.capture.av.MUXED_PCM_CAPTURE_POLICY

const val MUXED_VOICE_SOURCE = MUXED_PCM_CAPTURE_POLICY
const val MUXED_VOICE_LIMIT_MS = 10_000L

data class MuxedVoiceDecodedAudio(val wav: ByteArray, val audioOffsetMs: Int, val source: String = MUXED_VOICE_SOURCE)
data class MuxedVoiceSubmission(val video: File, val audio: MuxedVoiceDecodedAudio)

internal fun muxedVoiceReady(recordedDurationNs: Long, audioActive: Boolean, audioError: Boolean): Boolean =
    recordedDurationNs > 0 && audioActive && !audioError

internal fun voiceFinalizeAccepted(muxedVoice: Boolean, controlledDurationCap: Boolean, noError: Boolean, durationLimitReached: Boolean, audioFault: Boolean = false): Boolean =
    !audioFault && noError && !durationLimitReached && (!muxedVoice || controlledDurationCap)

/** One native container, one finalized source, and at most one submission per capture attempt. */
class MuxedVoiceCapture(
    private val scope: CoroutineScope,
    private val startRecording: () -> Boolean,
    private val awaitReady: suspend () -> Boolean,
    private val awaitVideo: suspend () -> VideoResult,
    private val stopRecording: () -> Unit,
    private val decode: suspend (File) -> MuxedVoiceDecodedAudio,
    private val onFinished: (MuxedVoiceSubmission) -> Unit,
    private val onFailure: (VoiceCaptureFailure) -> Unit,
    private val failureReason: () -> VoiceCaptureFailure = { VoiceCaptureFailure.Camera },
) {
    private val _phase = MutableStateFlow(VoiceCapturePhase.Idle)
    val phase: StateFlow<VoiceCapturePhase> = _phase
    private var worker: Job? = null
    private var generation = 0L
    private var active = false
    private var nativeStarted = false
    private var stopped = false
    private var finishRequested = false

    fun start() {
        if (active || _phase.value != VoiceCapturePhase.Idle || !scope.isActive) return
        active = true
        nativeStarted = false
        stopped = false
        finishRequested = false
        val attempt = ++generation
        _phase.value = VoiceCapturePhase.Preparing
        worker = scope.launch(start = CoroutineStart.LAZY) {
            var failure = VoiceCaptureFailure.Camera
            try {
                nativeStarted = startRecording()
                if (!nativeStarted) { fail(failure); return@launch }
                val ready = awaitReady()
                currentCoroutineContext().ensureActive()
                if (!active || attempt != generation) return@launch
                if (!ready) { fail(failureReason()); return@launch }
                _phase.value = VoiceCapturePhase.Recording
                val video = awaitVideo()
                currentCoroutineContext().ensureActive()
                if (!active || attempt != generation) return@launch
                if (video !is VideoResult.Ready) { fail(failureReason()); return@launch }
                // A safety cap or unexpected native EOF is not the user's completed reading.
                if (!finishRequested) { fail(VoiceCaptureFailure.DurationLimit); return@launch }
                _phase.value = VoiceCapturePhase.Finished
                stopOnce()
                failure = VoiceCaptureFailure.Audio
                val audio = decode(video.file)
                currentCoroutineContext().ensureActive()
                if (!active || attempt != generation) return@launch
                check(audio.wav.isNotEmpty() && audio.audioOffsetMs in -5000..5000 && audio.source == MUXED_VOICE_SOURCE)
                active = false
                onFinished(MuxedVoiceSubmission(video.file, audio))
            } catch (cancelled: CancellationException) {
                if (attempt == generation) cancel()
                throw cancelled
            } catch (_: Exception) {
                if (attempt == generation) fail(failure)
            }
        }
        worker?.start()
    }

    fun finish() {
        if (_phase.value == VoiceCapturePhase.Preparing) { cancel(); return }
        if (!active || _phase.value != VoiceCapturePhase.Recording) return
        finishRequested = true
        _phase.value = VoiceCapturePhase.Finished
        stopOnce()
    }

    fun cancel() {
        if (!active) return
        active = false
        generation++
        worker?.cancel()
        worker = null
        stopOnce()
        _phase.value = VoiceCapturePhase.Idle
    }

    private fun fail(failure: VoiceCaptureFailure) {
        if (!active) return
        active = false
        generation++
        worker?.cancel()
        worker = null
        stopOnce()
        _phase.value = VoiceCapturePhase.Failed
        onFailure(failure)
    }

    private fun stopOnce() {
        if (nativeStarted && !stopped) {
            stopped = true
            runCatching { stopRecording() }
        }
    }
}
