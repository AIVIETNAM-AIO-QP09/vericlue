package vn.vericlue.app.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.theme.Vc
import kotlin.math.abs

/** A single slow demonstration, then a held pose. The adjacent title carries the instruction. */
@Composable
fun HeadMotionGuide(direction: TurnDir?, progress: Float, modifier: Modifier = Modifier) {
    val colors = Vc.colors
    val motion = Vc.motion
    // A mirrored selfie: the user's left is also the left of this illustration.
    val target = when (direction) { TurnDir.Left -> -1f; TurnDir.Right -> 1f; null -> 0f }
    val complete = progress.isFinite() && progress >= 1f
    val yaw = remember { Animatable(if (direction == null && motion.enabled) -0.85f else 0f) }
    LaunchedEffect(direction, motion.enabled, complete) {
        if (!motion.enabled || complete) yaw.snapTo(target)
        else yaw.animateTo(target, tween(1100, delayMillis = 120, easing = FastOutSlowInEasing))
    }
    val measured = if (progress.isFinite()) progress.coerceIn(0f, 1f) else 0f
    val hold by animateFloatAsState(measured, motion.tween(140), label = "head-hold")
    val pose = if (!motion.enabled || complete) target else yaw.value
    val accent = if (complete) colors.ok else colors.accent
    Canvas(modifier.size(120.dp, 64.dp).clearAndSetSemantics {}) {
        val unit = minOf(size.width / 120f, size.height / 64f)
        withTransform({
            translate((size.width - 120f * unit) / 2f, (size.height - 64f * unit) / 2f)
            scale(unit, unit, pivot = Offset.Zero)
        }) {
            drawRoundRect(colors.surfaceSubtle, size = Size(120f, 64f), cornerRadius = CornerRadius(24f))
            val cx = 60f + pose * 3f
            val faceWidth = 29f - abs(pose) * 4f
            val shoulder = Path().apply {
                moveTo(cx - 22f, 52f)
                cubicTo(cx - 21f, 42f, cx - 10f, 42f, cx - 7f, 38f)
                lineTo(cx + 7f, 38f)
                cubicTo(cx + 10f, 42f, cx + 21f, 42f, cx + 22f, 52f)
                close()
            }
            drawPath(shoulder, accent.copy(alpha = 0.12f))
            drawOval(
                Brush.linearGradient(listOf(accent.copy(alpha = 0.24f), colors.surfaceSubtle),
                    Offset(cx - 15f, 10f), Offset(cx + 14f, 41f)),
                Offset(cx - faceWidth / 2f, 8f), Size(faceWidth, 34f),
            )
            drawOval(accent, Offset(cx - faceWidth / 2f, 8f), Size(faceWidth, 34f),
                style = Stroke(1.8f))
            // The facial midline/nose moves across the silhouette, communicating rotation.
            val mid = cx + pose * 7.5f
            val bridge = Path().apply {
                moveTo(mid, 17f)
                quadraticTo(mid + pose * 1.5f, 23f, mid + pose * 3f, 27f)
                quadraticTo(mid + pose, 29f, mid - 1f, 29f)
            }
            drawPath(bridge, accent, style = Stroke(1.6f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            val nearEye = 1.5f + abs(pose) * 0.3f
            val farEye = 1.5f - abs(pose) * 0.7f
            val eyeGap = 5.5f - abs(pose) * 1.5f
            drawCircle(accent, if (pose > 0) nearEye else farEye, Offset(mid - eyeGap, 21f))
            drawCircle(accent, if (pose < 0) nearEye else farEye, Offset(mid + eyeGap, 21f))
            drawLine(accent.copy(alpha = 0.75f), Offset(mid - 3f, 33f), Offset(mid + 3f, 33f),
                strokeWidth = 1.5f, cap = StrokeCap.Round)

            if (direction != null) {
                // Wide curved arrow is legible while the head is settling or motion is disabled.
                val sign = if (direction == TurnDir.Left) -1f else 1f
                fun x(value: Float) = if (sign > 0) value else 120f - value
                val arrow = Path().apply {
                    moveTo(x(28f), 39f)
                    cubicTo(x(43f), 57f, x(78f), 57f, x(98f), 38f)
                    moveTo(x(89f), 39f)
                    lineTo(x(98f), 38f)
                    lineTo(x(97f), 47f)
                }
                drawPath(arrow, accent, style = Stroke(2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            } else {
                for (sign in listOf(-1f, 1f)) {
                    val arrow = Path().apply {
                        moveTo(60f + sign * 38f, 28f)
                        lineTo(60f + sign * 23f, 28f)
                        moveTo(60f + sign * 28f, 23f)
                        lineTo(60f + sign * 23f, 28f)
                        lineTo(60f + sign * 28f, 33f)
                    }
                    drawPath(arrow, accent, style = Stroke(2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                }
            }
            // This is measured pose hold, not a timer or an invented verification percentage.
            drawLine(colors.border, Offset(43f, 59f), Offset(77f, 59f), 2.4f, StrokeCap.Round)
            if (hold > 0f) drawLine(accent, Offset(43f, 59f), Offset(43f + 34f * hold, 59f), 2.4f, StrokeCap.Round)
            if (complete) {
                drawCircle(colors.ok, 7f, Offset(105f, 13f))
                drawPath(Path().apply {
                    moveTo(102f, 13f); lineTo(104f, 15f); lineTo(108f, 11f)
                }, colors.surface, style = Stroke(1.8f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
    }
}
