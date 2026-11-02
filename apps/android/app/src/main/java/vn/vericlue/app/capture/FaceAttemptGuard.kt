package vn.vericlue.app.capture

enum class FaceAttemptIssue { FaceLost, ActionIncomplete, TimeLimit }

/** Local capture guard, never an identity decision. Issued video-relative times remain unchanged. */
class FaceAttemptGuard(private val timeline: FaceTimeline) {
    private var missingSince: Long? = null
    private var identity: Int? = null
    private var segment = -1
    private var action: HeadActionGate? = null
    private var failed: FaceAttemptIssue? = null
    val actionProgress: Float get() = action?.progress ?: 0f

    fun update(phase: FaceTimeline.Phase, signal: FaceSignal?, nowMs: Long): FaceAttemptIssue? {
        failed?.let { return it }
        if (!QualityGate.hasCompleteFace(signal, nowMs)) {
            val since = missingSince ?: nowMs.also { missingSince = it }
            // During adaptive head guidance a temporary detection/pose problem is corrected
            // inline. The bounded capture controller never completes with missing evidence.
            val correctingHead = timeline.adaptiveHead && phase is FaceTimeline.Phase.Head
            if ((!correctingHead && nowMs - since >= 450) || phase == FaceTimeline.Phase.Done ||
                signal?.faces?.let { it > 1 } == true) return fail(FaceAttemptIssue.FaceLost)
        } else {
            missingSince = null
            val id = signal?.trackingId
            if (identity != null && identity != id) return fail(FaceAttemptIssue.FaceLost)
            if (identity == null) identity = id
        }
        if (phase is FaceTimeline.Phase.Head &&
            (phase.segment !in timeline.headTurns.indices || phase.dir != timeline.headTurns[phase.segment])) {
            return fail(FaceAttemptIssue.ActionIncomplete)
        }
        if (timeline.adaptiveHead && phase is FaceTimeline.Phase.Head && phase.segment != segment) {
            // A late UI frame must not skip an unchecked direction.
            if (phase.segment != segment + 1 || (segment >= 0 && action?.complete != true)) {
                return fail(FaceAttemptIssue.ActionIncomplete)
            }
            segment = phase.segment
            action = HeadActionGate(phase.dir)
        }
        if (timeline.adaptiveHead && phase is FaceTimeline.Phase.Head) action?.update(signal, nowMs)
        // Legacy timed coaching remains advisory; only an adaptive plan adds local hold completion.
        if (timeline.adaptiveHead && phase == FaceTimeline.Phase.Done && timeline.headTurns.isNotEmpty() &&
            (segment != timeline.headTurns.lastIndex || action?.complete != true)) {
            return fail(FaceAttemptIssue.ActionIncomplete)
        }
        return null
    }

    private fun fail(issue: FaceAttemptIssue): FaceAttemptIssue = issue.also { failed = it }
}
