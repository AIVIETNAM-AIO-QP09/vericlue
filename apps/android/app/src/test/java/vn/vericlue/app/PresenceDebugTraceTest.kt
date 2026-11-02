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

    @Test fun analyzerTraceUsesFramePhaseAndRecordsDeliveryDelay() {
        val trace = PresenceDebugTrace(enabled = true)
        val demo = vn.vericlue.app.capture.FaceTimeline.demo(listOf(HeadTurnDirection.Left, HeadTurnDirection.Right))
        val timeline = vn.vericlue.app.capture.FaceTimeline(demo.slots, demo.frontalAtMs, demo.gaze,
            demo.headTurns, demo.headStartMs, demo.headDurationMs)
        val origin = 100_000.0
        val frameRel = timeline.headStartMs + 4950L
        val face = vn.vericlue.app.capture.FaceSignal(1, .45f, .5f, .45f, 26f, 120f,
            ((origin + frameRel) * 1_000_000).toLong())
        val event = trace.recordAnalyzerFrame(face, timeline, origin, origin + frameRel + 500)!!
        assertEquals(0, event.segmentIndex) // Frame belongs to previous segment, not its delivery phase.
        assertEquals(500L, event.frameAgeMs)
        assertEquals(frameRel, event.frameRelMs)
        assertEquals(HeadTurnDirection.Left, event.expectedDirection)
    }

    @Test fun adaptiveTraceFollowsActualCueBoundariesAndKeepsDelayedFramesInOldDirection() {
        val trace = PresenceDebugTrace(enabled = true, minSampleGapMs = 0)
        val timeline = vn.vericlue.app.capture.FaceTimeline.demo(listOf(HeadTurnDirection.Left, HeadTurnDirection.Right))
        val origin = 100_000.0
        val start = timeline.headStartMs.toLong()
        fun sample(frameAt: Long, deliveredAt: Long = frameAt) = trace.recordAnalyzerFrame(
            vn.vericlue.app.capture.FaceSignal(1, .45f, .5f, .45f, 26f, 120f,
                ((origin + frameAt) * 1_000_000).toLong()),
            timeline, origin, origin + deliveredAt,
        )!!
        // No observed cue must never be invented from an elapsed scheduled slot.
        assertEquals(-1, sample(start + 100).segmentIndex)
        trace.recordPhaseBoundary(start, "head", 0, HeadTurnDirection.Left)
        assertEquals(0, sample(start + 9000).segmentIndex)
        assertEquals(HeadTurnDirection.Left, sample(start + 9000).expectedDirection)
        trace.recordPhaseBoundary(start + 10000, "head", 1, HeadTurnDirection.Right)
        val delayed = sample(start + 9950, start + 10500)
        assertEquals(0, delayed.segmentIndex)
        assertEquals(550L, delayed.frameAgeMs)
        assertEquals(1, sample(start + 10100).segmentIndex)
        assertEquals(HeadTurnDirection.Right, sample(start + 10100).expectedDirection)
        // After nominal timed end, the active adaptive cue remains attributable.
        assertEquals(1, sample(start + 13000).segmentIndex)
        trace.clear()
        assertEquals(-1, sample(start + 13100).segmentIndex)
    }

    @Test fun traceJsonKeepsNoNonfiniteNumbersOrPrivateFields() {
        val trace = PresenceDebugTrace(enabled = true)
        trace.recordFaceSample(100, Float.NaN, Float.POSITIVE_INFINITY, 0f, null, 0)
        trace.recordGuidance(120, 0, "Warn", false)
        val json = kotlinx.serialization.json.Json.parseToJsonElement(trace.toJson()).toString()
        assertTrue(!json.contains("NaN") && !json.contains("Infinity"))
        assertTrue(json.contains("Warn"))
        assertTrue(!json.contains("session_id") && !json.contains("token") && !json.contains("image"))
        trace.clear()
        assertTrue(trace.snapshot().isEmpty())
        assertNull(PresenceDebugTrace(enabled = false).recordGuidance(0, 0, "Hold", false))
    }

    @Test fun attemptBindingContainsOnlyDigestAndIsCleared() {
        val trace = PresenceDebugTrace(enabled = true)
        trace.bindAttempt("synthetic-public-attempt")
        val value = trace.toJson()
        assertTrue(value.contains("attempt_sha256"))
        assertTrue(!value.contains("synthetic-public-attempt"))
        trace.clear()
        assertTrue(!trace.toJson().contains("attempt_sha256"))
    }
}
