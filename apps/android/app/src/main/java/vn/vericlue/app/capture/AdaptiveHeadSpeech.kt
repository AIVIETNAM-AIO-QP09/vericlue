package vn.vericlue.app.capture

import vn.vericlue.app.flow.TurnDir

/** Maps local adaptive feedback to the fixed, debounced guidance vocabulary. */
fun adaptiveHeadCue(state: HeadCaptureState): HeadCue? {
    if (state.done || state.issue != null) return null
    return when (state.feedback) {
        HeadFeedback.FaceMissing, HeadFeedback.MultipleFaces -> HeadCue.FindFace
        HeadFeedback.Level -> HeadCue.Straighten
        HeadFeedback.EaseBack -> HeadCue.EaseBack
        // A side acknowledgement must keep the pose until the controller changes segment.
        HeadFeedback.Hold, HeadFeedback.Complete -> HeadCue.Hold
        HeadFeedback.Turn, HeadFeedback.Further, HeadFeedback.WrongDirection -> when (state.direction) {
            TurnDir.Left -> HeadCue.Left
            TurnDir.Right -> HeadCue.Right
            null -> HeadCue.Center
        }
    }
}
