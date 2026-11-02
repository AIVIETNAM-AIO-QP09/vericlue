package vn.vericlue.app.capture

import android.os.SystemClock
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.TurnDir
import kotlin.math.abs

/**
 * One clock for every timestamp sent to the server (plan §4): elapsedRealtime, in ms.
 * Camera frames use the same base when the sensor timestamp source is REALTIME.
 */
object CaptureClock {
    fun nowMs(): Double = SystemClock.elapsedRealtimeNanos() / 1e6

    /** Choreographer/withFrameNanos times use System.nanoTime(); shift them onto elapsedRealtime. */
    fun frameNanosToMs(frameNanos: Long): Double =
        (frameNanos + (SystemClock.elapsedRealtimeNanos() - System.nanoTime())) / 1e6
}

/** What the face analyzer reports for one camera frame. Coordinates are 0..1 of the upright image. */
data class FaceSignal(
    val faces: Int,
    val widthFraction: Float,
    val centerX: Float,
    val centerY: Float,
    val yaw: Float,
    val luma: Float,
    val timestampNs: Long,
    val heightFraction: Float = 0f,
    val imageWidth: Int = 0,
    val imageHeight: Int = 0,
    val pitch: Float = Float.NaN,
    val roll: Float = Float.NaN,
    val landmarksComplete: Boolean = false,
    /** Nose, mouth and at least one eye are visible in side poses. */
    val landmarksVisible: Boolean = false,
    /** Local monotonic time when this frame entered analysis, independent of the sensor clock. */
    val observedAtMs: Long = -1L,
    val trackingId: Int? = null,
) {
    val left: Float get() = centerX - widthFraction / 2
    val right: Float get() = centerX + widthFraction / 2
    val top: Float get() = centerY - heightFraction / 2
    val bottom: Float get() = centerY + heightFraction / 2
}

/** Turns a face signal into the single quality hint shown on the framing screen. */
object QualityGate {
    // Capture guidance only. These checks never replace the server's verification decision.
    const val MIN_LUMA = 70f
    const val MIN_FACE_WIDTH = 0.24f
    // ML Kit recommends at least 100x100 pixels per face; avoid a fixed distance on every lens.
    const val MIN_FACE_PIXELS = 100f
    // A side pose projects narrower than the same face held at the same distance.
    const val MIN_TRACKED_FACE_WIDTH = 0.20f
    const val MAX_FACE_WIDTH = 0.90f
    const val MAX_FACE_HEIGHT = 0.90f
    const val EDGE_MARGIN = 0.02f
    const val MAX_CENTER_OFFSET = 0.18f
    const val GOOD_HOLD_MS = 1000L
    const val MAX_FRAME_AGE_MS = 500L
    const val MAX_FRONTAL_YAW = 12f
    const val MAX_FRONTAL_PITCH = 15f
    const val MAX_ROLL = 15f

    fun isFresh(s: FaceSignal?, nowMs: Long): Boolean = s != null && s.observedAtMs >= 0 &&
        nowMs - s.observedAtMs in 0..MAX_FRAME_AGE_MS

    private fun geometryValid(s: FaceSignal): Boolean =
        s.imageWidth > 0 && s.imageHeight > 0 &&
            listOf(s.widthFraction, s.heightFraction, s.centerX, s.centerY, s.yaw, s.pitch, s.roll, s.luma).all { it.isFinite() } &&
            s.widthFraction > 0 && s.heightFraction > 0

    private fun fullyInsideImage(s: FaceSignal): Boolean =
        s.left >= EDGE_MARGIN && s.top >= EDGE_MARGIN &&
            s.right <= 1f - EDGE_MARGIN && s.bottom <= 1f - EDGE_MARGIN

    /** Full, fresh single-face evidence; unlike readiness, side turns are permitted here. */
    fun hasCompleteFace(s: FaceSignal?, nowMs: Long): Boolean =
        s != null && isFresh(s, nowMs) && s.faces == 1 && geometryValid(s) &&
            fullyInsideImage(s) && s.landmarksVisible && s.widthFraction >= MIN_TRACKED_FACE_WIDTH &&
            s.widthFraction <= MAX_FACE_WIDTH && s.heightFraction <= MAX_FACE_HEIGHT &&
            abs(s.roll) <= MAX_ROLL && abs(s.pitch) <= MAX_FRONTAL_PITCH

    fun evaluate(s: FaceSignal?, nowMs: Long = SystemClock.elapsedRealtime()): FramingState = when {
        s == null || !isFresh(s, nowMs) || s.faces <= 0 -> FramingState.NoFace
        s.faces != 1 -> FramingState.MultipleFaces
        !geometryValid(s) -> FramingState.IncompleteFace
        s.luma < MIN_LUMA -> FramingState.LowLight
        s.widthFraction > MAX_FACE_WIDTH || s.heightFraction > MAX_FACE_HEIGHT -> FramingState.TooClose
        !fullyInsideImage(s) || !s.landmarksComplete -> FramingState.IncompleteFace
        s.widthFraction < MIN_FACE_WIDTH || s.widthFraction * s.imageWidth < MIN_FACE_PIXELS ||
            s.heightFraction * s.imageHeight < MIN_FACE_PIXELS -> FramingState.TooFar
        abs(s.yaw) > MAX_FRONTAL_YAW || abs(s.pitch) > MAX_FRONTAL_PITCH || abs(s.roll) > MAX_ROLL -> FramingState.NotStraight
        abs(s.centerX - 0.5f) > MAX_CENTER_OFFSET || abs(s.centerY - 0.45f) > MAX_CENTER_OFFSET -> FramingState.OffCenter
        else -> FramingState.Good
    }
}

/** Head-turn check for task 2: turn past the threshold, hold briefly, then face forward again. */
class TurnTracker(
    private val thresholdDeg: Float = 25f,
    private val holdMs: Long = 300,
    private val straightDeg: Float = 10f,
    private val direction: TurnDir = TurnDir.Left,
) {
    private var turnedSinceMs: Long? = null
    var turned = false
        private set

    /** Returns true once the turn is complete (turned, then back to straight). */
    fun update(yaw: Float, nowMs: Long): Boolean {
        if (!yaw.isFinite()) { turnedSinceMs = null; turned = false; return false }
        if (!turned) {
            if (if (direction == TurnDir.Left) yaw >= thresholdDeg else yaw <= -thresholdDeg) {
                val since = turnedSinceMs ?: nowMs.also { turnedSinceMs = it }
                if (nowMs - since >= holdMs) turned = true
            } else {
                turnedSinceMs = null
            }
            return false
        }
        return abs(yaw) <= straightDeg
    }
}

/** One colour on screen during the light challenge (ADR-0016 layer 1). [index] is null for grey. */
data class ColorSlot(val index: Int?, val rgb: String, val durationMs: Int)

object ColorSchedule {
    // From packages/contracts/chromapulse.json (baseline colour, tail, safety limit).
    const val BASELINE_RGB = "#d1d1d1"
    const val TAIL_MS = 500
    const val MAX_CHANGES_PER_SECOND = 2.5
    private val PALETTE = listOf("#ffcc73", "#73d9ff", "#ffb3eb", "#80e09e")

    /** Grey baseline, the server's 8 steps (hold + transition), then a grey tail. */
    fun from(challenge: Challenge): List<ColorSlot> = buildList {
        add(ColorSlot(null, BASELINE_RGB, challenge.baselineMs))
        challenge.colorSequence.forEachIndexed { i, step -> add(ColorSlot(i, step.rgb, step.holdMs + step.transitionMs)) }
        add(ColorSlot(null, BASELINE_RGB, TAIL_MS))
    }

    /** Offline demo only: a local sequence with the same shape. Real runs always use the server's. */
    fun demo(): List<ColorSlot> = buildList {
        add(ColorSlot(null, BASELINE_RGB, 1000))
        repeat(8) { add(ColorSlot(it, PALETTE[(it * 3 + 1) % PALETTE.size], 550)) }
        add(ColorSlot(null, BASELINE_RGB, TAIL_MS))
    }

    /** No coloured step may be shorter than the flicker safety limit allows. */
    fun isSafe(slots: List<ColorSlot>): Boolean =
        slots.filter { it.index != null }.all { it.durationMs >= 1000.0 / MAX_CHANGES_PER_SECOND }

    fun parse(rgb: String): Int = (0xFF000000L or rgb.removePrefix("#").toLong(16)).toInt()
}
