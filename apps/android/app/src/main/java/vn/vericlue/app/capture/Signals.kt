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
)

/** Turns a face signal into the single quality hint shown on the framing screen. */
object QualityGate {
    // Starting values for the scaffold; tune on real phones (plan, phase 9).
    const val MIN_LUMA = 70f
    const val MIN_FACE_WIDTH = 0.32f
    const val MAX_CENTER_OFFSET = 0.18f
    const val GOOD_HOLD_MS = 1000L

    fun evaluate(s: FaceSignal?): FramingState = when {
        s == null || s.faces == 0 -> FramingState.NoFace
        s.luma < MIN_LUMA -> FramingState.LowLight
        s.widthFraction < MIN_FACE_WIDTH -> FramingState.TooFar
        abs(s.centerX - 0.5f) > MAX_CENTER_OFFSET || abs(s.centerY - 0.45f) > MAX_CENTER_OFFSET -> FramingState.OffCenter
        else -> FramingState.Good
    }
}

/** Head-turn check for task 2: turn past the threshold, hold briefly, then face forward again. */
class TurnTracker(private val thresholdDeg: Float = 25f, private val holdMs: Long = 300, private val straightDeg: Float = 10f) {
    private var turnedSinceMs: Long? = null
    var turned = false
        private set

    /** Returns true once the turn is complete (turned, then back to straight). */
    fun update(yaw: Float, nowMs: Long): Boolean {
        // The sign of yaw for left/right must be checked on a real front camera; any side counts for now.
        if (!turned) {
            if (abs(yaw) >= thresholdDeg) {
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

/**
 * Assistive live hint during scheduled head turns. Purely advisory UI feedback;
 * never gates completion or overrides the server's detector decision.
 *
 * ML Kit Face.headEulerAngleY is positive when the face turns toward the right side of the
 * processed image. CameraSession passes unmirrored front-camera frames to InputImage.fromMediaImage,
 * so user-left (TurnDir.Left) turns toward the right of the unmirrored image (yaw > 0) and
 * user-right (TurnDir.Right) turns toward the left of the unmirrored image (yaw < 0).
 */
object HeadTurnGuide {
    const val TURN_MIN_DEG = 18f
    const val TURN_MAX_SAFE_DEG = 40f
    const val CENTER_MAX_DEG = 12f
    const val MAX_TURN_OFFSET = 0.24f

    fun guidanceText(
        dir: TurnDir?,
        face: FaceSignal?,
        returnToCenter: Boolean = false,
        remainingSeconds: Int? = null,
    ): String {
        if (face != null) {
            if (face.faces == 0) return "Đưa khuôn mặt vào khung"
            if (face.faces > 1) return "Chỉ để một khuôn mặt trong khung"
            val offFrame = abs(face.centerX - 0.5f) > MAX_TURN_OFFSET || abs(face.centerY - 0.45f) > MAX_TURN_OFFSET
            return if (dir == null) {
                val absYaw = abs(face.yaw)
                when {
                    offFrame -> "Đưa khuôn mặt vào giữa khung hình"
                    absYaw > CENTER_MAX_DEG -> "Quay về giữa, nhìn thẳng vào camera"
                    else -> "Giữ yên, nhìn thẳng vào camera"
                }
            } else {
                val signedYaw = if (dir == TurnDir.Left) face.yaw else -face.yaw
                when {
                    signedYaw > TURN_MAX_SAFE_DEG -> "Quay vừa phải, giữ mặt trong khung"
                    signedYaw < TURN_MIN_DEG -> "Quay chậm theo hướng mũi tên"
                    offFrame -> "Quay vừa phải, giữ mặt trong khung"
                    returnToCenter -> "Quay chậm, sau đó nhìn thẳng"
                    else -> "Giữ hướng này đến khi đổi hướng dẫn"
                }
            }
        }
        return when {
            dir == null -> "Giữ yên, nhìn thẳng vào camera"
            returnToCenter -> "Quay chậm, sau đó nhìn thẳng"
            else -> "Quay chậm theo hướng mũi tên"
        }
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
