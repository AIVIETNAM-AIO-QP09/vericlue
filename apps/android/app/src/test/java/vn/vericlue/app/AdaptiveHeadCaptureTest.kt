package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.TurnDir

class AdaptiveHeadCaptureTest {
    private fun frame(at: Long, yaw: Float = 0f) = FaceSignal(
        1, .4f, .5f, .5f, yaw, 120f, (at * 1_000_000).coerceAtLeast(1L),
        heightFraction = .5f, imageWidth = 480, imageHeight = 640,
        pitch = 0f, roll = 0f, landmarksComplete = true, landmarksVisible = true,
        observedAtMs = at, trackingId = 7,
    )
    private fun capture() = AdaptiveHeadCapture(listOf(TurnDir.Left, TurnDir.Right, null), 30000.0)

    @Test fun standingStillForSeveralOldSlotsKeepsFirstInstructionAndHints() {
        val capture = capture()
        for (at in 0L..8000L step 100) {
            val state = capture.update(frame(at), at, at.toDouble())
            assertEquals(0, state.segment)
            assertNull(state.issue)
            assertFalse(state.done)
            assertEquals(HeadFeedback.Further, state.feedback)
        }
    }

    @Test fun wrongTurnThenCorrectTurnContinuesSameAttempt() {
        val capture = capture()
        for (at in 0L..4000L step 100) {
            val state = capture.update(frame(at, -26f), at, at.toDouble())
            assertEquals(HeadFeedback.WrongDirection, state.feedback)
            assertEquals(0f, state.progress, 0f)
            assertNull(state.issue)
        }
        for (at in 4100L..4800L step 100) capture.update(frame(at, 26f), at, at.toDouble())
        val next = capture.update(frame(5100, 26f), 5100, 5100.0)
        assertEquals(1, next.segment)
        assertEquals(TurnDir.Right, next.direction)
        assertFalse(next.done)
    }

    @Test fun allThreeCommandsRequireSeparateFreshHolds() {
        val capture = capture()
        for (at in 0L..700L step 100) capture.update(frame(at, 26f), at, at.toDouble())
        assertEquals(1, capture.update(frame(1000, 26f), 1000, 1000.0).segment)
        for (at in 1100L..1800L step 100) capture.update(frame(at, -26f), at, at.toDouble())
        assertEquals(2, capture.update(frame(2100, -26f), 2100, 2100.0).segment)
        for (at in 2200L..5000L step 100) {
            assertFalse(capture.update(frame(at, -26f), at, at.toDouble()).done)
        }
        for (at in 5100L..5800L step 100) capture.update(frame(at), at, at.toDouble())
        assertTrue(capture.update(frame(6100), 6100, 6100.0).done)
    }

    @Test fun missingOrClippedFaceShowsCorrectionAndDoesNotAdvance() {
        for (bad in listOf<FaceSignal?>(null, frame(0).copy(centerY = .1f), frame(0).copy(landmarksVisible = false))) {
            val state = capture().update(bad, 0, 0.0)
            assertEquals(HeadFeedback.FaceMissing, state.feedback)
            assertNull(state.issue)
            assertFalse(state.done)
        }
    }

    @Test fun frozenFrameOrOverrotationCannotComplete() {
        val capture = capture()
        for (at in 0L..8000L step 100) {
            val state = capture.update(frame(0, 26f), at, at.toDouble())
            assertEquals(0, state.segment)
            assertFalse(state.done)
        }
        for (at in 8100L..10000L step 100) {
            val state = capture.update(frame(at, 60f), at, at.toDouble())
            assertEquals(HeadFeedback.EaseBack, state.feedback)
            assertEquals(0f, state.progress, 0f)
        }
    }

    @Test fun wrongPoseResetsOnlyCurrentHold() {
        val capture = capture()
        for (at in 0L..500L step 100) capture.update(frame(at, 26f), at, at.toDouble())
        assertEquals(0f, capture.update(frame(600, -26f), 600, 600.0).progress, 0f)
        for (at in 700L..1200L step 100) assertEquals(0, capture.update(frame(at, 26f), at, at.toDouble()).segment)
        assertEquals(HeadFeedback.Hold, capture.update(frame(1300, 26f), 1300, 1300.0).feedback)
    }

    @Test fun deadlineIsBoundedAndNeverPassesWithoutActions() {
        val capture = capture()
        val timeout = capture.update(frame(30000), 30000, 30000.0)
        assertEquals(FaceAttemptIssue.TimeLimit, timeout.issue)
        assertFalse(timeout.done)
        assertEquals(FaceAttemptIssue.TimeLimit, capture.update(frame(30100, 26f), 30100, 30100.0).issue)
    }

    @Test fun rehearsalAndAdaptiveCaptureUseTheSamePoseBand() {
        for (yaw in listOf(16f, 20f, 29f)) {
            val capture = capture()
            assertEquals(TurnPoseState.Hold, HeadTurnGuide.evaluatePose(TurnDir.Left, frame(0, yaw)))
            for (at in 0L..700L step 100) capture.update(frame(at, yaw), at, at.toDouble())
            assertEquals(1, capture.update(frame(1000, yaw), 1000, 1000.0).segment)
        }
        for (yaw in listOf(30f, 45f)) {
            val capture = capture()
            for (at in 0L..1000L step 100) {
                val state = capture.update(frame(at, yaw), at, at.toDouble())
                assertEquals(HeadFeedback.EaseBack, state.feedback)
                assertEquals(0, state.segment)
                assertEquals(0f, state.progress, 0f)
            }
        }
        assertEquals(HeadFeedback.Level, capture().update(frame(0, 20f).copy(pitch = 13f), 0, 0.0).feedback)
    }

    @Test fun missingFaceDuringAcknowledgementCannotFinishOrSkipToNextCommand() {
        val capture = capture()
        for (at in 0L..700L step 100) capture.update(frame(at, 26f), at, at.toDouble())
        val lost = capture.update(null, 1000, 1000.0)
        assertEquals(0, lost.segment)
        assertEquals(HeadFeedback.FaceMissing, lost.feedback)
        assertEquals(0f, lost.progress, 0f)
    }
}
