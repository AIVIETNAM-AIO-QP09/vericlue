package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Test
import vn.vericlue.app.capture.HeadCaptureState
import vn.vericlue.app.capture.HeadCue
import vn.vericlue.app.capture.HeadFeedback
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.screens.adaptiveHeadCue

/** The spoken instruction must agree with the gate that controls step advancement. */
class AdaptiveHeadCueTest {
    private fun cue(feedback: HeadFeedback, direction: TurnDir? = TurnDir.Left) =
        adaptiveHeadCue(HeadCaptureState(0, direction, 0f, feedback))

    @Test fun unfinishedTurnKeepsRequestedDirection() {
        for (feedback in listOf(HeadFeedback.Turn, HeadFeedback.Further, HeadFeedback.WrongDirection)) {
            assertEquals(HeadCue.Left, cue(feedback, TurnDir.Left))
            assertEquals(HeadCue.Right, cue(feedback, TurnDir.Right))
            assertEquals(HeadCue.Center, cue(feedback, null))
        }
    }

    @Test fun holdAcknowledgementDoesNotAskToTurnBackBeforeStepAdvances() {
        for (direction in listOf(TurnDir.Left, TurnDir.Right, null)) {
            assertEquals(HeadCue.Hold, cue(HeadFeedback.Hold, direction))
            assertEquals(HeadCue.Hold, cue(HeadFeedback.Complete, direction))
        }
    }

    @Test fun unsafePoseOverridesRequestedDirection() {
        assertEquals(HeadCue.FindFace, cue(HeadFeedback.FaceMissing))
        assertEquals(HeadCue.FindFace, cue(HeadFeedback.MultipleFaces))
        assertEquals(HeadCue.Straighten, cue(HeadFeedback.Level))
        assertEquals(HeadCue.EaseBack, cue(HeadFeedback.EaseBack))
    }
}
