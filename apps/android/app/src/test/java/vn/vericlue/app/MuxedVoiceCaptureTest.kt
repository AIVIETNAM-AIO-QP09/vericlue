package vn.vericlue.app

import java.io.File
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import vn.vericlue.app.capture.*

@OptIn(ExperimentalCoroutinesApi::class)
class MuxedVoiceCaptureTest {
    @get:Rule val temp = TemporaryFolder()

    @Test fun readinessRequiresPositiveVideoAndActiveErrorFreeNativeAudio() {
        assertFalse(muxedVoiceReady(1, audioActive = false, audioError = false))
        assertFalse(muxedVoiceReady(0, audioActive = true, audioError = false))
        assertFalse(muxedVoiceReady(1, audioActive = true, audioError = true))
        assertTrue(muxedVoiceReady(1, audioActive = true, audioError = false))
    }

    @Test fun nativeDurationCapIsNeverACompletedReading() {
        assertFalse(voiceFinalizeAccepted(true, true, noError = false, durationLimitReached = true))
        assertFalse(voiceFinalizeAccepted(false, true, noError = false, durationLimitReached = true))
        assertFalse(voiceFinalizeAccepted(true, false, noError = false, durationLimitReached = true))
        assertFalse(voiceFinalizeAccepted(true, true, noError = false, durationLimitReached = false))
        assertTrue(voiceFinalizeAccepted(false, false, noError = true, durationLimitReached = false))
    }

    @Test fun finalAudioFaultCannotBeAcceptedEvenWithACleanOrControlledCapEvent() {
        assertFalse(voiceFinalizeAccepted(true, true, noError = true, durationLimitReached = false, audioFault = true))
        assertFalse(voiceFinalizeAccepted(true, true, noError = false, durationLimitReached = true, audioFault = true))
    }

    @Test fun preparingWaitsForNativeReadinessAndPreservesOneSourceFileAndSignedOffset() = runTest {
        val ready = CompletableDeferred<Boolean>()
        val finalized = CompletableDeferred<VideoResult>()
        val result = Results()
        val file = temp.newFile("shared.mp4").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        var decodedFile: File? = null
        val wav = byteArrayOf(4, 5)
        val capture = MuxedVoiceCapture(backgroundScope,
            { result.starts++; true }, { ready.await() }, { finalized.await() }, { result.stops++ },
            { decodedFile = it; MuxedVoiceDecodedAudio(wav, -160) }, result::finished, result::failed)
        capture.start()
        capture.start()
        assertEquals(VoiceCapturePhase.Preparing, capture.phase.value)
        runCurrent()
        assertEquals(1, result.starts)
        assertNull(decodedFile)
        ready.complete(true)
        runCurrent()
        assertEquals(VoiceCapturePhase.Recording, capture.phase.value)
        capture.finish()
        capture.finish()
        assertEquals(VoiceCapturePhase.Finished, capture.phase.value)
        assertTrue(result.submissions.isEmpty())
        finalized.complete(VideoResult.Ready(file))
        runCurrent()
        capture.cancel()
        assertEquals(1, result.stops)
        assertEquals(file, decodedFile)
        assertSame(file, result.submissions.single().video)
        assertSame(wav, result.submissions.single().audio.wav)
        assertEquals(-160, result.submissions.single().audio.audioOffsetMs)
        assertEquals("muxed-av-pcm-v3-ptsgrid", result.submissions.single().audio.source)
        assertArrayEquals(byteArrayOf(1, 2, 3), file.readBytes())
        assertTrue(result.errors.isEmpty())
    }

    @Test fun nativeDurationCompletionWithoutExplicitFinishNeverDecodesOrPublishes() = runTest {
        val finalized = CompletableDeferred<VideoResult>()
        val result = Results()
        var decodes = 0
        val capture = MuxedVoiceCapture(backgroundScope, { true }, { true }, { finalized.await() },
            { result.stops++ }, { decodes++; MuxedVoiceDecodedAudio(byteArrayOf(1), 139) }, result::finished, result::failed)
        capture.start()
        runCurrent()
        finalized.complete(VideoResult.Ready(temp.newFile("capped.mp4")))
        runCurrent()
        capture.finish()
        assertEquals(0, decodes)
        assertTrue(result.submissions.isEmpty())
        assertEquals("DurationLimit", result.errors.single().name)
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(1, result.stops)
    }

    @Test fun explicitFinishBeforeNativeFinalizePublishesExactlyOnce() = runTest {
        val finalized = CompletableDeferred<VideoResult>()
        val result = Results()
        var decodes = 0
        val capture = MuxedVoiceCapture(backgroundScope, { true }, { true }, { finalized.await() },
            { result.stops++ }, { decodes++; MuxedVoiceDecodedAudio(byteArrayOf(1), 139) }, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.finish()
        finalized.complete(VideoResult.Ready(temp.newFile("finished.mp4")))
        runCurrent()
        capture.finish()
        assertEquals(1, decodes)
        assertEquals(1, result.submissions.size)
        assertEquals(1, result.stops)
        assertTrue(result.errors.isEmpty())
    }

    @Test fun cancelDuringNativePreparationCannotDecodeOrSubmitLater() = runTest {
        val ready = CompletableDeferred<Boolean>()
        val result = Results()
        var decodes = 0
        val capture = MuxedVoiceCapture(backgroundScope, { result.starts++; true },
            { withContext(NonCancellable) { ready.await() } }, { VideoResult.Ready(temp.newFile()) },
            { result.stops++ }, { decodes++; MuxedVoiceDecodedAudio(byteArrayOf(1), 0) }, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.cancel()
        capture.cancel()
        ready.complete(true)
        runCurrent()
        assertEquals(VoiceCapturePhase.Idle, capture.phase.value)
        assertEquals(1, result.starts)
        assertEquals(1, result.stops)
        assertEquals(0, decodes)
        assertTrue(result.submissions.isEmpty())
        assertTrue(result.errors.isEmpty())
    }

    @Test fun cancelDuringDecodeRejectsALateResultFromTheOldAttempt() = runTest {
        val decoding = CompletableDeferred<MuxedVoiceDecodedAudio>()
        val finalized = CompletableDeferred<VideoResult>()
        val result = Results()
        val file = temp.newFile("cancel.mp4")
        val capture = MuxedVoiceCapture(backgroundScope, { true }, { true }, { finalized.await() },
            { result.stops++ }, { withContext(NonCancellable) { decoding.await() } }, result::finished, result::failed)
        capture.start()
        runCurrent()
        capture.finish()
        finalized.complete(VideoResult.Ready(file))
        runCurrent()
        assertEquals(VoiceCapturePhase.Finished, capture.phase.value)
        capture.cancel()
        decoding.complete(MuxedVoiceDecodedAudio(byteArrayOf(1), 0))
        runCurrent()
        assertEquals(1, result.stops)
        assertTrue(file.exists())
        assertTrue(result.submissions.isEmpty())
        assertTrue(result.errors.isEmpty())
    }

    @Test fun nativeReadinessFailureClosesTheContainerAndNeverAdvertisesRecording() = runTest {
        val result = Results()
        val capture = MuxedVoiceCapture(backgroundScope, { true }, { false }, { error("Must not await a rejected capture") },
            { result.stops++ }, { error("Must not decode") }, result::finished, result::failed,
            failureReason = { VoiceCaptureFailure.Audio })
        capture.start()
        runCurrent()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(listOf(VoiceCaptureFailure.Audio), result.errors)
        assertEquals(1, result.stops)
        assertTrue(result.submissions.isEmpty())
    }

    @Test fun rejectedStartDoesNotStopAnotherAttemptsContainer() = runTest {
        val result = Results()
        val capture = MuxedVoiceCapture(backgroundScope, { false }, { error("Must not wait") },
            { error("Must not finalize") }, { result.stops++ }, { error("Must not decode") }, result::finished, result::failed)
        capture.start()
        runCurrent()
        assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
        assertEquals(listOf(VoiceCaptureFailure.Camera), result.errors)
        assertEquals(0, result.stops)
        assertTrue(result.submissions.isEmpty())
    }

    @Test fun absentFailedOrTimedOutFinalizeCannotReachTheDecoder() = runTest {
        for (video in listOf(VideoResult.NotRecorded, VideoResult.Timeout)) {
            val result = Results()
            val capture = MuxedVoiceCapture(backgroundScope, { true }, { true }, { video },
                { result.stops++ }, { error("Must not decode") }, result::finished, result::failed)
            capture.start()
            runCurrent()
            assertEquals(listOf(VoiceCaptureFailure.Camera), result.errors)
            assertTrue(result.submissions.isEmpty())
            assertEquals(1, result.stops)
        }
    }

    @Test fun decoderFailureOrUnrepresentableOffsetFailsClosedWithoutClamping() = runTest {
        for (mode in 0..3) {
            val result = Results()
            val finalized = CompletableDeferred<VideoResult>()
            val capture = MuxedVoiceCapture(backgroundScope, { true }, { true }, { finalized.await() },
                { result.stops++ }, {
                    when (mode) {
                        0 -> error("Decoder rejected the track")
                        1 -> MuxedVoiceDecodedAudio(byteArrayOf(1), -5001)
                        2 -> MuxedVoiceDecodedAudio(byteArrayOf(), 0)
                        else -> MuxedVoiceDecodedAudio(byteArrayOf(1), 0, source = "unknown")
                    }
                }, result::finished, result::failed)
            capture.start()
            runCurrent()
            capture.finish()
            finalized.complete(VideoResult.Ready(temp.newFile()))
            runCurrent()
            assertEquals(listOf(VoiceCaptureFailure.Audio), result.errors)
            assertEquals(VoiceCapturePhase.Failed, capture.phase.value)
            assertTrue(result.submissions.isEmpty())
        }
    }

    private class Results {
        var starts = 0
        var stops = 0
        val submissions = mutableListOf<MuxedVoiceSubmission>()
        val errors = mutableListOf<VoiceCaptureFailure>()
        fun finished(result: MuxedVoiceSubmission) { submissions += result }
        fun failed(error: VoiceCaptureFailure) { errors += error }
    }
}
