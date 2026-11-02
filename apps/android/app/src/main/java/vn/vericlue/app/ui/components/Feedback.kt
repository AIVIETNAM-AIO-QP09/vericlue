package vn.vericlue.app.ui.components

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import vn.vericlue.app.R
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc

/** Uses Android's haptic setting; no vibration permission or custom waveform. */
@Composable
fun CompletionHaptic(completed: Boolean, eventKey: Any = Unit) {
    val view = LocalView.current
    LaunchedEffect(completed, eventKey) {
        if (completed && !view.isInEditMode) view.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
    }
}

/** Static brand/check remains visible while the decorative Lottie ring loads or fails. */
@Composable
internal fun SuccessMark() {
    val c = Vc.colors
    Box(Modifier.size(112.dp)) {
        Box(Modifier.size(104.dp).clip(CircleShape).background(Palette.LogoNavy), contentAlignment = Alignment.Center) {
            Image(painterResource(R.drawable.logo_mark), contentDescription = null, modifier = Modifier.width(56.dp))
        }
        Box(
            Modifier.align(Alignment.BottomEnd).offset(x = (-2).dp, y = (-2).dp).size(40.dp).clip(CircleShape)
                .background(c.okBg).border(3.dp, c.background, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(24.dp)) {
                val stroke = 2.5.dp.toPx()
                val path = Path().apply {
                    moveTo(size.width * 0.26f, size.height * 0.51f)
                    lineTo(size.width * 0.43f, size.height * 0.67f)
                    lineTo(size.width * 0.75f, size.height * 0.34f)
                }
                drawPath(path, c.success, style = Stroke(stroke, cap = StrokeCap.Round))
            }
        }
    }
}
