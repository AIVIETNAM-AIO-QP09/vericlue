package vn.vericlue.app.capture

import androidx.compose.ui.geometry.Rect
import vn.vericlue.app.flow.FramingState
import kotlin.math.cos
import kotlin.math.sin

enum class GuideAlignment { Unavailable, TooFar, TooClose, OffCenter, Good }

/**
 * The oval aligns a face; full sensor bounds and all frontal landmarks are checked separately.
 * Small outline tolerance accommodates detector-box jitter, with bounded hysteresis during hold.
 * Minimum fill is local composition guidance; it does not change server model thresholds.
 */
fun faceGuideAlignment(face: Rect?, guide: Rect?, retainingAlignment: Boolean = false): GuideAlignment {
    if (face == null || guide == null || face.isEmpty || guide.isEmpty ||
        listOf(face.left, face.top, face.right, face.bottom, guide.left, guide.top, guide.right, guide.bottom).any { !it.isFinite() }) {
        return GuideAlignment.Unavailable
    }
    val allowance = if (retainingAlignment) 1.10f else 1.06f
    if (face.width > guide.width * allowance || face.height > guide.height * allowance) return GuideAlignment.TooClose
    val rx = guide.width / 2 * allowance
    val ry = guide.height / 2 * allowance
    val fits = (0 until 32).all { i ->
        val angle = i * Math.PI / 16
        val x = (face.center.x + face.width / 2 * cos(angle) - guide.center.x) / rx
        val y = (face.center.y + face.height / 2 * sin(angle) - guide.center.y) / ry
        x * x + y * y <= 1.0
    }
    if (!fits) return GuideAlignment.OffCenter
    val minimumFill = if (retainingAlignment) 0.60f else 0.65f
    if (face.width / guide.width < minimumFill || face.height / guide.height < minimumFill) return GuideAlignment.TooFar
    return GuideAlignment.Good
}

fun faceFitsGuide(face: Rect?, guide: Rect?): Boolean = faceGuideAlignment(face, guide) == GuideAlignment.Good

data class FramingFeedback(
    val state: FramingState,
    val progress: Float = 0f,
    val ready: Boolean = false,
    val preparingCamera: Boolean = false,
)

/** One framing decision for hints, outline and capture, without competing distance instructions. */
class FramingAlignmentGate {
    private val stable = StableFaceGate()
    private var aligned = false

    fun reset() { aligned = false; stable.reset() }

    fun acceptsLatest(signal: FaceSignal?, nowMs: Long, face: Rect?, guide: Rect?): Boolean =
        QualityGate.evaluate(signal, nowMs) == FramingState.Good &&
            faceGuideAlignment(face, guide, retainingAlignment = aligned) == GuideAlignment.Good

    fun update(signal: FaceSignal?, nowMs: Long, face: Rect?, guide: Rect?): FramingFeedback {
        val quality = QualityGate.evaluate(signal, nowMs)
        if (quality != FramingState.Good) {
            reset()
            return FramingFeedback(quality)
        }
        when (faceGuideAlignment(face, guide, retainingAlignment = aligned)) {
            GuideAlignment.Unavailable -> {
                reset()
                return FramingFeedback(FramingState.NoFace, preparingCamera = true)
            }
            GuideAlignment.TooFar -> {
                reset()
                return FramingFeedback(FramingState.TooFar)
            }
            GuideAlignment.TooClose -> {
                reset()
                return FramingFeedback(FramingState.TooClose)
            }
            GuideAlignment.OffCenter -> {
                reset()
                return FramingFeedback(FramingState.OffCenter)
            }
            GuideAlignment.Good -> aligned = true
        }
        val ready = stable.update(signal, nowMs)
        return FramingFeedback(FramingState.Good, stable.progress, ready)
    }
}
