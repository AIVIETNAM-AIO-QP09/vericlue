package vn.vericlue.app.ui.components

import android.view.HapticFeedbackConstants
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.keyframes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Vc

/** Uses Android's haptic setting; no vibration permission or custom waveform. */
@Composable
fun CompletionHaptic(completed: Boolean, eventKey: Any = Unit) {
    val view = LocalView.current
    LaunchedEffect(completed, eventKey) {
        if (completed && !view.isInEditMode) view.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
    }
}

/** A single settling motion and a drawn check, never an indefinite celebration. */
@Composable
fun SuccessBadge() {
    val c = Vc.colors
    val motion = Vc.motion
    val scale = remember { Animatable(if (motion.enabled) 0.9f else 1f) }
    val check = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) {
        if (!motion.enabled) scale.snapTo(1f) else scale.animateTo(1f, keyframes {
            durationMillis = 420
            0.9f at 0
            1.04f at 260
            1f at 420
        })
    }
    LaunchedEffect(motion.enabled) { check.animateTo(1f, motion.tween(320, 70)) }
    Box(Modifier.size(96.dp).scale(if (motion.enabled) scale.value else 1f).clip(CircleShape).background(c.okBg), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(44.dp)) {
            val stroke = 3.dp.toPx()
            drawCircle(c.ok, radius = (size.minDimension - stroke) / 2f, style = Stroke(stroke))
            val path = Path().apply {
                moveTo(size.width * 0.26f, size.height * 0.51f)
                lineTo(size.width * 0.43f, size.height * 0.67f)
                lineTo(size.width * 0.75f, size.height * 0.34f)
            }
            val measure = PathMeasure().apply { setPath(path, false) }
            val segment = Path()
            measure.getSegment(0f, measure.length * if (motion.enabled) check.value else 1f, segment, true)
            drawPath(segment, c.ok, style = Stroke(stroke, cap = StrokeCap.Round))
        }
    }
}
