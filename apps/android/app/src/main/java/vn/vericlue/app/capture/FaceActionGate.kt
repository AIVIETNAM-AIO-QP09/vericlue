package vn.vericlue.app.capture

import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.TurnDir
import kotlin.math.abs

/** Consecutive distinct analysis frames, never repeated UI polls or elapsed time alone. */
private class StableFrameHold(private val holdMs: Long, private val minimumFrames: Int) {
    private var firstObservedMs: Long? = null
    private var lastObservedMs: Long? = null
    private var lastFrameNs: Long? = null
    private var trackingId: Int? = null
    private var frames = 0
    var progress: Float = 0f
        private set

    fun reset() {
        firstObservedMs = null
        lastObservedMs = null
        lastFrameNs = null
        trackingId = null
        frames = 0
        progress = 0f
    }

    fun update(s: FaceSignal?, nowMs: Long, valid: Boolean): Boolean {
        if (!valid || s == null || !QualityGate.isFresh(s, nowMs)) { reset(); return false }
        val previous = lastObservedMs
        if (previous != null && (s.observedAtMs < previous || s.observedAtMs - previous > QualityGate.MAX_FRAME_AGE_MS ||
                (trackingId != null && trackingId != s.trackingId))) reset()
        if (lastFrameNs == s.timestampNs) return false
        if (lastFrameNs != null && s.timestampNs < lastFrameNs!!) { reset(); return false }
        if (lastObservedMs != null && s.observedAtMs <= lastObservedMs!!) return false
        firstObservedMs = firstObservedMs ?: s.observedAtMs
        lastObservedMs = s.observedAtMs
        lastFrameNs = s.timestampNs
        trackingId = s.trackingId
        frames++
        val duration = s.observedAtMs - firstObservedMs!!
        progress = minOf(duration.toFloat() / holdMs, frames.toFloat() / minimumFrames).coerceIn(0f, 1f)
        return duration >= holdMs && frames >= minimumFrames
    }
}

/** One complete frontal face held for a second; UI guide containment is supplied by the caller. */
class StableFaceGate {
    private val hold = StableFrameHold(QualityGate.GOOD_HOLD_MS, minimumFrames = 5)
    val progress: Float get() = hold.progress
    fun reset() = hold.reset()
    fun update(s: FaceSignal?, nowMs: Long, insideGuide: Boolean = true): Boolean =
        hold.update(s, nowMs, insideGuide && QualityGate.evaluate(s, nowMs) == FramingState.Good)
}

/**
 * Evidence for one server-issued head segment. Success is latched only until this gate is reset.
 * ML Kit +Y points right in the unmirrored image: subject-left, matching the server convention.
 * The mirrored PreviewView must not reverse the detector signal.
 * Source: developers.google.com/android/reference/com/google/mlkit/vision/face/Face#getHeadEulerAngleY()
 */
class HeadActionGate(
    val direction: TurnDir?,
    private val thresholdDeg: Float = 25f,
    private val straightDeg: Float = 10f,
    holdMs: Long = 350L,
) {
    private val hold = StableFrameHold(holdMs, minimumFrames = 3)
    var complete: Boolean = false
        private set
    val progress: Float get() = if (complete) 1f else hold.progress

    fun reset() { complete = false; hold.reset() }

    fun update(s: FaceSignal?, nowMs: Long): Boolean {
        if (complete) return true
        val poseMatches = s != null && when (direction) {
            TurnDir.Left -> s.yaw >= thresholdDeg
            TurnDir.Right -> s.yaw <= -thresholdDeg
            null -> abs(s.yaw) <= straightDeg
        }
        complete = hold.update(s, nowMs, poseMatches && QualityGate.hasCompleteFace(s, nowMs))
        return complete
    }
}
