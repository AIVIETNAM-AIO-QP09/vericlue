package vn.vericlue.app.capture

import kotlin.math.abs
import vn.vericlue.app.flow.TurnDir

/** Corrective guidance is local only; the server independently checks the recorded movement. */
enum class HeadFeedback { Turn, Further, WrongDirection, Hold, Complete, FaceMissing, MultipleFaces, Level, EaseBack }

data class HeadCaptureState(
    val segment: Int,
    val direction: TurnDir?,
    val progress: Float,
    val feedback: HeadFeedback,
    val done: Boolean = false,
    val issue: FaceAttemptIssue? = null,
)

/** Advances by fresh observed holds, never by a timed slot or by UI polling alone. */
class AdaptiveHeadCapture(private val order: List<TurnDir?>, private val deadlineMs: Double) {
    private var segment = 0
    private var gate = newGate()
    private var completeAt: Long? = null
    private var failed: FaceAttemptIssue? = null
    private var finished = false

    init { require(order.isNotEmpty() && deadlineMs.isFinite() && deadlineMs > 0) }

    private fun newGate() = HeadActionGate(
        direction = order.getOrNull(segment), straightDeg = HeadTurnGuide.CENTER_MAX_DEG, holdMs = 650L,
    )

    fun update(signal: FaceSignal?, nowMs: Long, videoMs: Double): HeadCaptureState {
        fun state(feedback: HeadFeedback, issue: FaceAttemptIssue? = failed) = HeadCaptureState(
            segment, order[segment], gate.progress, feedback, finished, issue,
        )
        if (failed != null) return state(HeadFeedback.Turn)
        if (finished) return state(HeadFeedback.Complete)
        if (!videoMs.isFinite() || videoMs >= deadlineMs) {
            failed = FaceAttemptIssue.TimeLimit
            return state(HeadFeedback.Turn)
        }
        // Keep a short acknowledgement before changing the instruction. The next direction
        // starts with a fresh gate, so the same frame cannot satisfy two commands.
        if (completeAt != null) {
            if (!QualityGate.hasCompleteFace(signal, nowMs) ||
                (segment == order.lastIndex && (signal == null || abs(signal.yaw) > HeadTurnGuide.CENTER_MAX_DEG))) {
                completeAt = null
                gate.reset()
            } else if (nowMs - completeAt!! >= 250L) {
                if (segment == order.lastIndex) {
                    finished = true
                    return state(HeadFeedback.Complete)
                }
                segment++
                gate = newGate()
                completeAt = null
                return state(HeadFeedback.Turn)
            } else return state(HeadFeedback.Complete)
        }
        val feedback = when {
            signal == null || !QualityGate.isFresh(signal, nowMs) || signal.faces == 0 -> HeadFeedback.FaceMissing
            signal.faces > 1 -> HeadFeedback.MultipleFaces
            !signal.pitch.isFinite() || !signal.roll.isFinite() ||
                abs(signal.pitch) > HeadTurnGuide.MAX_TILT_DEG || abs(signal.roll) > HeadTurnGuide.MAX_TILT_DEG -> HeadFeedback.Level
            !QualityGate.hasCompleteFace(signal, nowMs) -> HeadFeedback.FaceMissing
            abs(signal.yaw) > HeadTurnGuide.TURN_MAX_SAFE_DEG -> HeadFeedback.EaseBack
            order[segment] == TurnDir.Left && signal.yaw < -10f ||
                order[segment] == TurnDir.Right && signal.yaw > 10f -> HeadFeedback.WrongDirection
            order[segment] == null && abs(signal.yaw) > HeadTurnGuide.CENTER_MAX_DEG -> HeadFeedback.Turn
            order[segment] != null && abs(signal.yaw) < HeadTurnGuide.TURN_MIN_DEG -> HeadFeedback.Further
            else -> HeadFeedback.Hold
        }
        // Invalid/over-rotated poses reset the current hold but keep the requested direction.
        if (feedback == HeadFeedback.Hold) {
            if (gate.update(signal, nowMs)) {
                completeAt = nowMs
                return state(HeadFeedback.Complete)
            }
        } else gate.reset()
        return state(feedback)
    }
}

fun HeadCaptureState.hint(): String = when (feedback) {
    HeadFeedback.FaceMissing -> "Đưa mặt vào khung"
    HeadFeedback.MultipleFaces -> "Chỉ một người trong khung"
    HeadFeedback.Level -> "Giữ đầu thẳng"
    HeadFeedback.EaseBack -> "Quay nhẹ về giữa"
    HeadFeedback.Hold -> "Giữ yên trong giây lát"
    HeadFeedback.Complete -> "Đã ghi nhận tư thế"
    HeadFeedback.WrongDirection -> if (direction == TurnDir.Left) "Vui lòng quay sang trái" else "Vui lòng quay sang phải"
    HeadFeedback.Further -> if (direction == TurnDir.Left) "Quay thêm sang trái" else "Quay thêm sang phải"
    HeadFeedback.Turn -> when (direction) {
        TurnDir.Left -> "Từ từ quay đầu sang trái"
        TurnDir.Right -> "Từ từ quay đầu sang phải"
        null -> "Đưa mặt về chính diện"
    }
}
