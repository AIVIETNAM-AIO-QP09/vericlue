package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.vericlue.app.capture.FaceAttemptIssue
import vn.vericlue.app.capture.HeadCaptureState
import vn.vericlue.app.capture.HeadCue
import vn.vericlue.app.capture.HeadCuePolicy
import vn.vericlue.app.capture.HeadFeedback
import vn.vericlue.app.capture.adaptiveHeadCue
import vn.vericlue.app.flow.TurnDir

class AdaptiveHeadSpeechTest {
    @Test fun movementCorrectionsKeepTheRequestedDirection() {
        for (feedback in listOf(HeadFeedback.Turn, HeadFeedback.Further, HeadFeedback.WrongDirection)) {
            assertEquals(HeadCue.Left, adaptiveHeadCue(state(feedback, TurnDir.Left)))
            assertEquals(HeadCue.Right, adaptiveHeadCue(state(feedback, TurnDir.Right)))
            assertEquals(HeadCue.Center, adaptiveHeadCue(state(feedback, null)))
        }
    }

    @Test fun holdAndSideAcknowledgementNeverAskForAPrematureReturn() {
        for (feedback in listOf(HeadFeedback.Hold, HeadFeedback.Complete)) {
            assertEquals(HeadCue.Hold, adaptiveHeadCue(state(feedback, TurnDir.Left)))
            assertEquals(HeadCue.Hold, adaptiveHeadCue(state(feedback, TurnDir.Right)))
            assertEquals(HeadCue.Hold, adaptiveHeadCue(state(feedback, null)))
        }
    }

    @Test fun safetyFeedbackMapsToPriorityWarnings() {
        assertEquals(HeadCue.FindFace, adaptiveHeadCue(state(HeadFeedback.FaceMissing)))
        assertEquals(HeadCue.FindFace, adaptiveHeadCue(state(HeadFeedback.MultipleFaces)))
        assertEquals(HeadCue.Straighten, adaptiveHeadCue(state(HeadFeedback.Level)))
        assertEquals(HeadCue.EaseBack, adaptiveHeadCue(state(HeadFeedback.EaseBack)))
    }

    @Test fun terminalStatesNeverIssueAnotherMovementCommand() {
        assertNull(adaptiveHeadCue(state(HeadFeedback.Complete).copy(done = true)))
        assertNull(adaptiveHeadCue(state(HeadFeedback.Turn).copy(issue = FaceAttemptIssue.TimeLimit)))
    }

    @Test fun stableProgressAndAcknowledgementDoNotRestartSpeech() {
        val policy = HeadCuePolicy()
        val spoken = mutableListOf<HeadCue>()
        var stops = 0
        for ((index, feedback) in listOf(HeadFeedback.Hold, HeadFeedback.Hold, HeadFeedback.Complete).withIndex()) {
            val observed = state(feedback).copy(progress = index / 2f)
            adaptiveHeadCue(observed)?.let { cue ->
                policy.dispatch(observed.segment, cue, index * 100L, { stops++ }, { spoken += it })
            }
        }
        assertEquals(listOf(HeadCue.Hold), spoken)
        assertEquals(1, stops)
    }

    @Test fun changingSegmentImmediatelyReplacesThePreviousCue() {
        val policy = HeadCuePolicy()
        val spoken = mutableListOf<HeadCue>()
        for ((index, observed) in listOf(state(HeadFeedback.Hold), state(HeadFeedback.Turn, TurnDir.Right).copy(segment = 1)).withIndex()) {
            adaptiveHeadCue(observed)?.let { cue -> policy.dispatch(observed.segment, cue, index * 100L, {}, { spoken += it }) }
        }
        assertEquals(listOf(HeadCue.Hold, HeadCue.Right), spoken)
    }

    @Test fun warningCancelsHoldAndRecoveryWaitsForStableFeedback() {
        val policy = HeadCuePolicy()
        val spoken = mutableListOf<HeadCue>()
        var stops = 0
        for ((at, observed) in listOf(0L to state(HeadFeedback.Hold), 100L to state(HeadFeedback.Level),
            200L to state(HeadFeedback.Hold), 400L to state(HeadFeedback.Hold), 500L to state(HeadFeedback.Hold))) {
            adaptiveHeadCue(observed)?.let { policy.dispatch(observed.segment, it, at, { stops++ }, { spoken += it }) }
        }
        assertEquals(listOf(HeadCue.Hold, HeadCue.Straighten, HeadCue.Hold), spoken)
        assertEquals(3, stops)
    }

    private fun state(feedback: HeadFeedback, direction: TurnDir? = TurnDir.Left) =
        HeadCaptureState(segment = 0, direction = direction, progress = 0f, feedback = feedback)
}
