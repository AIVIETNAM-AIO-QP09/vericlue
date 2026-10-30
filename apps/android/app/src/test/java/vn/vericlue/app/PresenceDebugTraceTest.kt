package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.HeadTurnDirection
import vn.vericlue.app.capture.PresenceDebugTrace

class PresenceDebugTraceTest {
    @Test
    fun disabledTraceKeepsNoSamples() {
        val trace = PresenceDebugTrace(enabled = false)
        trace.recordFaceSample(
            recordingRelMs = 1_500L,
            yaw = 26f,
            pitch = 2f,
            roll = 1f,
            expectedDirection = HeadTurnDirection.Left,
            holdMs = 120L,
        )
        assertTrue(trace.snapshot().isEmpty())
    }

    @Test
    fun traceIsBoundedAndClearedBetweenAttempts() {
        val trace = PresenceDebugTrace(enabled = true, maxSamples = 8, minSampleGapMs = 100L)
        repeat(20) { index ->
            trace.recordGazeTarget(
                recordingRelMs = index * 50L,
                dotX = 0.25f,
                dotY = 0.75f,
            )
        }
        assertTrue(trace.snapshot().size <= 8)
        trace.clear()
        assertTrue(trace.snapshot().isEmpty())
    }

    @Test
    fun staleSampleCannotBeAttributedToNewSegment() {
        val trace = PresenceDebugTrace(enabled = true, minSampleGapMs = 0L)
        val accepted = trace.recordFaceSampleForWindow(
            recordingRelMs = 3_950L,
            windowStartRelMs = 4_000L,
            windowEndRelMs = 8_000L,
            yaw = 28f,
            pitch = 0f,
            roll = 0f,
            expectedDirection = HeadTurnDirection.Right,
            holdMs = 200L,
        )
        assertNull(accepted)
        assertEquals(0, trace.snapshot().size)
    }
}

