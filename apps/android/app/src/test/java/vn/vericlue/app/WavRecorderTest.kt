package vn.vericlue.app

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.runCurrent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.PcmInput
import vn.vericlue.app.capture.AudioCaptureState
import vn.vericlue.app.capture.WavRecorder

@OptIn(ExperimentalCoroutinesApi::class)
class WavRecorderTest {
    @Test fun canceledScopeReleasesAudioBeforeTheReadLoopRuns() = runTest {
        val input = FakeInput()
        val scope = CoroutineScope(Job() + StandardTestDispatcher(testScheduler))
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        assertTrue(recorder.start(scope))
        scope.cancel()
        runCurrent()
        assertTrue(input.released)
        assertEquals(1, input.releases)
        assertEquals(AudioCaptureState.Failed, recorder.state.value)
        assertTrue(recorder.stop().isEmpty())
    }

    @Test fun reachingEightSecondsSignalsCompletionAndReleasesTheMicrophone() = runTest {
        val input = FakeInput()
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        assertTrue(recorder.start(backgroundScope))
        assertEquals(AudioCaptureState.Recording, recorder.state.value)
        runCurrent()
        assertEquals(AudioCaptureState.Completed, recorder.state.value)
        assertTrue(input.released)
        assertEquals(256_044, recorder.stop().size)
        recorder.stop()
        assertEquals(1, input.releases)
    }

    @Test fun stopDuringAnInFlightReadDiscardsLateBytes() = runTest {
        val input = FakeInput()
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        input.beforeRead = { recorder.stop() }
        assertTrue(recorder.start(backgroundScope))
        runCurrent()
        assertTrue(recorder.stop().isEmpty())
        assertEquals(AudioCaptureState.Idle, recorder.state.value)
        assertEquals(1, input.releases)
    }

    @Test fun duplicateStartDoesNotResetOrReopenTheRecording() = runTest {
        val input = FakeInput()
        var opens = 0
        val recorder = WavRecorder(inputFactory = { opens++; input }, dispatcher = StandardTestDispatcher(testScheduler))
        assertTrue(recorder.start(backgroundScope))
        assertTrue(recorder.start(backgroundScope))
        assertEquals(1, opens)
        recorder.stop()
        runCurrent()
        assertEquals(1, input.releases)
    }

    @Test fun readFailureEndsRecordingAndReleasesTheMicrophone() = runTest {
        val input = FakeInput(readError = true)
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        assertTrue(recorder.start(backgroundScope))
        runCurrent()
        assertEquals(AudioCaptureState.Failed, recorder.state.value)
        assertTrue(input.released)
        recorder.stop()
    }

    @Test fun unsuccessfulNativeStartNeverReportsReadyAndReleasesInput() = runTest {
        val input = FakeInput(starts = false)
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        try {
            assertFalse(recorder.start(backgroundScope))
            assertTrue(input.released)
        } finally { recorder.stop() }
    }

    @Test fun nativeStartExceptionNeverEscapesOrLeaksInput() = runTest {
        val input = FakeInput(startError = true)
        val recorder = WavRecorder(inputFactory = { input }, dispatcher = StandardTestDispatcher(testScheduler))
        try {
            assertFalse(recorder.start(backgroundScope))
            assertTrue(input.released)
        } finally { recorder.stop() }
    }

    private class FakeInput(val starts: Boolean = true, val startError: Boolean = false, val readError: Boolean = false) : PcmInput {
        override val bufferSize = 320
        override var recording = false
        var released = false
        var releases = 0
        var beforeRead: (() -> Unit)? = null
        override fun start() {
            if (startError) throw IllegalStateException("microphone unavailable")
            recording = starts
        }
        override fun read(buffer: ByteArray): Int {
            beforeRead?.invoke()
            if (readError) throw IllegalStateException("microphone lost")
            buffer.fill(1)
            return buffer.size
        }
        override fun stop() { recording = false }
        override fun release() { released = true; releases++ }
    }
}
