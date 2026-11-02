package vn.vericlue.app

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.VoiceCapture
import vn.vericlue.app.capture.VoiceCaptureFailure
import vn.vericlue.app.capture.VoiceCapturePhase

@OptIn(ExperimentalCoroutinesApi::class)
class VoiceCaptureTest {
    @Test fun leavingDuringRecordingClosesCaptureWithoutSubmitting() = runTest {
        val result = CaptureResult()
        var audioStops = 0
        var videoStops = 0
        val capture = VoiceCapture(backgroundScope, { true }, { true }, { audioStops++; byteArrayOf(1) }, { videoStops++ }, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.cancel()
        capture.cancel()
        capture.finish()
        assertEquals(VoiceCapturePhase.Idle, capture.phase.value)
        assertTrue(result.wavs.isEmpty())
        assertEquals(1, audioStops)
        assertEquals(1, videoStops)
    }

    @Test fun emptyAudioNeverUploadsAsACompletedAttempt() = runTest {
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { true }, { true }, { byteArrayOf() }, {}, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.finish()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(listOf(VoiceCaptureFailure.Audio), result.errors)
        assertTrue(result.wavs.isEmpty())
    }

    @Test fun offsetMarkerIsSampledAfterDelayedAudioStartup() = runTest {
        var videoElapsed = 33
        var markedOffset: Int? = null
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { true },
            { videoElapsed += 400; true }, { byteArrayOf(1) }, {}, result::finished, result::failed,
            onAudioReady = { markedOffset = videoElapsed; true })
        capture.start()
        assertEquals(null, markedOffset)
        runCurrent()
        assertEquals(433, markedOffset)
        assertEquals(VoiceCapturePhase.Recording, capture.phase.value)
        capture.cancel()
    }

    @Test fun missingVideoMarkerAfterAudioStartupCleansUpInsteadOfReportingReady() = runTest {
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { true }, { true }, { byteArrayOf(1) }, {}, result::finished, result::failed,
            onAudioReady = { false })
        capture.start()
        runCurrent()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(listOf(VoiceCaptureFailure.Camera), result.errors)
        assertTrue(result.wavs.isEmpty())
    }

    @Test fun readinessWaitsForVideoAndSuccessfulMicrophoneStart() = runTest {
        val video = CompletableDeferred<Boolean>()
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { video.await() }, { result.audioStarts++; true }, { byteArrayOf(1) }, {}, result::finished, result::failed)
        capture.start()
        assertEquals(VoiceCapturePhase.Preparing, capture.phase.value)
        runCurrent()
        assertEquals(0, result.audioStarts)
        video.complete(true)
        runCurrent()
        assertEquals(VoiceCapturePhase.Recording, capture.phase.value)
        assertEquals(1, result.audioStarts)
        capture.cancel()
    }

    @Test fun cameraTimeoutNeverStartsTheMicrophoneOrReportsReady() = runTest {
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { false }, { result.audioStarts++; true }, { byteArrayOf(1) }, {}, result::finished, result::failed)
        capture.start()
        runCurrent()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(0, result.audioStarts)
        assertEquals(listOf(VoiceCaptureFailure.Camera), result.errors)
        assertTrue(result.wavs.isEmpty())
    }

    @Test fun microphoneFailureNeverReportsReadyOrSubmits() = runTest {
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { true }, { false }, { byteArrayOf(1) }, {}, result::finished, result::failed)
        capture.start()
        runCurrent()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(listOf(VoiceCaptureFailure.Audio), result.errors)
        assertTrue(result.wavs.isEmpty())
    }

    @Test fun cancelDuringPreparationCannotStartLateAudioOrSubmit() = runTest {
        val video = CompletableDeferred<Boolean>()
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope,
            { withContext(NonCancellable) { video.await() } },
            { result.audioStarts++; true }, { byteArrayOf(1) }, {}, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.cancel()
        video.complete(true)
        runCurrent()
        assertEquals(VoiceCapturePhase.Idle, capture.phase.value)
        assertEquals(0, result.audioStarts)
        assertTrue(result.wavs.isEmpty())
        assertTrue(result.errors.isEmpty())
    }

    @Test fun manualStopAndAutomaticCompletionSubmitOnlyOnce() = runTest {
        val result = CaptureResult()
        var audioStops = 0
        var videoStops = 0
        val capture = VoiceCapture(backgroundScope, { true }, { true }, { audioStops++; byteArrayOf(7, 8) }, { videoStops++ }, result::finished, result::failed)
        capture.start()
        capture.start()
        runCurrent()
        capture.finish()
        capture.finish()
        capture.cancel() // navigation disposes the route after submission
        assertEquals(1, audioStops)
        assertEquals(1, videoStops)
        assertEquals(1, result.wavs.size)
        assertTrue(result.wavs.single().contentEquals(byteArrayOf(7, 8)))
    }

    @Test fun stopBeforeReadinessCancelsInsteadOfUploadingEmptyAudio() = runTest {
        val video = CompletableDeferred<Boolean>()
        val result = CaptureResult()
        val capture = VoiceCapture(backgroundScope, { video.await() }, { result.audioStarts++; true }, { byteArrayOf() }, {}, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.finish()
        video.complete(true)
        runCurrent()
        assertEquals(0, result.audioStarts)
        assertEquals(VoiceCapturePhase.Idle, capture.phase.value)
        assertTrue(result.wavs.isEmpty())
    }

    private class CaptureResult {
        var audioStarts = 0
        val wavs = mutableListOf<ByteArray>()
        val errors = mutableListOf<VoiceCaptureFailure>()
        fun finished(wav: ByteArray) { wavs += wav }
        fun failed(error: VoiceCaptureFailure) { errors += error }
    }
}
