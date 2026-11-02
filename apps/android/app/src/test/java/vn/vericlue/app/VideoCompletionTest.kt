package vn.vericlue.app

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import vn.vericlue.app.capture.VideoResult
import vn.vericlue.app.capture.awaitVideoFile
import vn.vericlue.app.capture.runningVideoElapsedMs

@OptIn(ExperimentalCoroutinesApi::class)
class VideoCompletionTest {
    @get:Rule val temporary = TemporaryFolder()

    private fun video() = temporary.newFile("video.mp4").apply { writeBytes(byteArrayOf(1, 2, 3)) }

    @Test fun statusThenFailedFinalizeCannotKeepTheCameraReadyForAudio() {
        val finalized = CompletableDeferred<Boolean>()
        val status = 100_000_000L to 1_000_000_000L
        assertEquals(300, runningVideoElapsedMs(true, status, finalized, 1_200_000_000L))
        finalized.complete(false)
        assertNull(runningVideoElapsedMs(true, status, finalized, 1_200_000_000L))
    }

    @Test fun evenSuccessfulFinalizeOrCancellationIsNoLongerRunningVideo() {
        val status = 100_000_000L to 1_000_000_000L
        assertNull(runningVideoElapsedMs(true, status, CompletableDeferred(true), 1_200_000_000L))
        val canceled = CompletableDeferred<Boolean>().apply { cancel() }
        assertNull(runningVideoElapsedMs(true, status, canceled, 1_200_000_000L))
    }

    @Test fun readinessNeedsBothALiveRecordingAndAStatusFrame() {
        val finalized = CompletableDeferred<Boolean>()
        val status = 100_000_000L to 1_000_000_000L
        assertNull(runningVideoElapsedMs(false, status, finalized, 1_200_000_000L))
        assertNull(runningVideoElapsedMs(true, null, finalized, 1_200_000_000L))
        assertNull(runningVideoElapsedMs(true, status, null, 1_200_000_000L))
    }

    @Test fun returnsTheFileOnlyAfterSuccessfulFinalize() = runTest {
        val file = video()
        assertEquals(VideoResult.Ready(file), awaitVideoFile(file, CompletableDeferred(true)))
    }

    @Test fun noRecordingIsNotATimeout() = runTest {
        assertEquals(VideoResult.NotRecorded, awaitVideoFile(null, null))
    }

    @Test fun aNonemptyUnfinalizedFileTimesOutAndStaysForRetry() = runTest {
        val file = video()
        val completion = CompletableDeferred<Boolean>()
        assertEquals(VideoResult.Timeout, awaitVideoFile(file, completion))
        assertEquals(3000L, testScheduler.currentTime)
        assertTrue(file.exists())
        assertEquals(3L, file.length())
        assertFalse(completion.isCancelled)
    }

    @Test fun retryWaitsForTheSameRecordingToFinish() = runTest {
        val file = video()
        val completion = CompletableDeferred<Boolean>()
        assertEquals(VideoResult.Timeout, awaitVideoFile(file, completion))
        completion.complete(true)
        assertEquals(VideoResult.Ready(file), awaitVideoFile(file, completion))
    }

    @Test fun failedFinalizeNeverReturnsTheFile() = runTest {
        val file = video()
        assertEquals(VideoResult.NotRecorded, awaitVideoFile(file, CompletableDeferred(false)))
    }

    @Test fun successfulFinalizeWithoutUsableBytesDoesNotReturnAFile() = runTest {
        val file = temporary.newFile("empty.mp4")
        assertEquals(VideoResult.NotRecorded, awaitVideoFile(file, CompletableDeferred(true)))
        file.delete()
        assertEquals(VideoResult.NotRecorded, awaitVideoFile(file, CompletableDeferred(true)))
    }
}
