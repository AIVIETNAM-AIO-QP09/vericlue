package vn.vericlue.app.capture

import androidx.compose.ui.geometry.Rect
import kotlin.math.cos
import kotlin.math.sin

enum class FaceAttemptIssue { FaceLost, ActionIncomplete }

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
            if (nowMs - since >= 450 || phase == FaceTimeline.Phase.Done) return fail(FaceAttemptIssue.FaceLost)
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
        if (phase is FaceTimeline.Phase.Head && phase.segment != segment) {
            // A late UI frame must not skip an unchecked direction.
            if (phase.segment != segment + 1 || (segment >= 0 && action?.complete != true)) {
                return fail(FaceAttemptIssue.ActionIncomplete)
            }
            segment = phase.segment
            action = HeadActionGate(phase.dir)
        }
        if (phase is FaceTimeline.Phase.Head) action?.update(signal, nowMs)
        if (phase == FaceTimeline.Phase.Done && timeline.headTurns.isNotEmpty() &&
            (segment != timeline.headTurns.lastIndex || action?.complete != true)) {
            return fail(FaceAttemptIssue.ActionIncomplete)
        }
        return null
    }

    private fun fail(issue: FaceAttemptIssue): FaceAttemptIssue = issue.also { failed = it }
}

/** Fits the whole detected face ellipse into the visible guide using CameraX-mapped bounds. */
fun faceFitsGuide(face: Rect?, guide: Rect?): Boolean {
    if (face == null || guide == null || face.isEmpty || guide.isEmpty ||
        listOf(face.left, face.top, face.right, face.bottom, guide.left, guide.top, guide.right, guide.bottom).any { !it.isFinite() }) return false
    val rx = guide.width * 0.48f
    val ry = guide.height * 0.48f
    return (0 until 16).all { i ->
        val angle = i * Math.PI / 8
        val x = (face.center.x + face.width / 2 * cos(angle) - guide.center.x) / rx
        val y = (face.center.y + face.height / 2 * sin(angle) - guide.center.y) / ry
        x * x + y * y <= 1.0
    }
}
