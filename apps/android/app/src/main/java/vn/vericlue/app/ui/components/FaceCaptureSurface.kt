package vn.vericlue.app.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

/** Phase-independent guide in full-window coordinates. Text/insets may adapt, never the phase. */
fun faceGuideRect(width: Float, height: Float, density: Float, fontScale: Float, topInset: Float, bottomInset: Float): Rect {
    val top = topInset + (128f + 32f * fontScale) * density
    val bottom = bottomInset + (84f + 32f * fontScale) * density
    val available = (height - top - bottom).coerceAtLeast(24f * density)
    val h = minOf(minOf(250f * density, width * 0.66f) * 1.32f, available)
    val w = h / 1.32f
    val center = (height * 0.46f).coerceIn(top + h / 2, maxOf(top + h / 2, height - bottom - h / 2))
    return Rect((width - w) / 2, center - h / 2, (width + w) / 2, center + h / 2)
}

/** The camera occupies the same full window in framing, colour, gaze and head-turn phases. */
@Composable
fun FaceCaptureSurface(
    title: String,
    hint: String,
    onStop: () -> Unit,
    background: Color = Palette.CameraBg,
    light: Boolean = false,
    progress: Float? = null,
    direction: TurnDir? = null,
    gaze: Offset? = null,
    good: Boolean = false,
    faceScale: Float = 1f,
    dim: Float = 0f,
    extraOverlay: @Composable () -> Unit = {},
) {
    BackHandler(onBack = onStop)
    VcTheme(dark = !light) {
        SystemBarIcons(background)
        StableCameraScene(faceScale = faceScale, dim = dim) {
            BoxWithConstraints(Modifier.fillMaxSize()) {
                val density = LocalDensity.current
                val top = WindowInsets.statusBars.getTop(density).toFloat()
                val bottom = WindowInsets.navigationBars.getBottom(density).toFloat()
                val oval = faceGuideRect(constraints.maxWidth.toFloat(), constraints.maxHeight.toFloat(),
                    density.density, density.fontScale, top, bottom)
                val ink = if (light) Palette.Ink else Color.White
                val ring = if (good) Palette.OkOnDark else if (light) Palette.Primary else Color.White
                CameraFeed(Modifier.fillMaxSize())
                Canvas(Modifier.fillMaxSize()) {
                    val mask = Path().apply { fillType = PathFillType.EvenOdd; addRect(Rect(Offset.Zero, size)); addOval(oval) }
                    drawPath(mask, background)
                }
                // Separate measurable guide: tests compare these actual bounds across every screen.
                Canvas(Modifier.offset(x = with(density) { oval.left.toDp() }, y = with(density) { oval.top.toDp() })
                    .size(with(density) { oval.width.toDp() }, with(density) { oval.height.toDp() }).testTag("face-guide")) {
                    drawOval(ring, style = Stroke(2.dp.toPx()))
                    progress?.let {
                        val pad = 7.dp.toPx()
                        drawArc(ring, -90f, 360 * it.coerceIn(0f, 1f), false,
                            Offset(-pad, -pad), Size(size.width + 2 * pad, size.height + 2 * pad), style = Stroke(3.dp.toPx()))
                    }
                }
                Column(Modifier.fillMaxWidth().statusBarsPadding()) {
                    TopBar(onStop)
                    StepProgress(2, stepLabel(2))
                    Text(title, style = VcType.titleMedium, color = ink, textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp))
                }
                if (direction != null) {
                    val left = if (direction == TurnDir.Left) oval.left - 20 * density.density else oval.right - 28 * density.density
                    Box(Modifier.offset(x = with(density) { left.toDp() }, y = with(density) { (oval.center.y - 24 * density.density).toDp() })
                        .size(48.dp).clip(CircleShape).background(Palette.LogoNavy), contentAlignment = Alignment.Center) {
                        Icon(if (direction == TurnDir.Left) Icons.AutoMirrored.Outlined.ArrowBack else Icons.AutoMirrored.Outlined.ArrowForward,
                            null, tint = Color.White, modifier = Modifier.size(28.dp))
                    }
                }
                Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding()
                    .padding(horizontal = 24.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(hint, style = VcType.bodySmall, color = ink, textAlign = TextAlign.Center)
                    SecondaryButton("Dừng xác minh", onStop)
                }
                // Keep server gaze coordinates relative to this full window, including system insets.
                gaze?.let {
                    Box(Modifier.offset(maxWidth * it.x - 24.dp, maxHeight * it.y - 24.dp).size(48.dp)
                        .testTag("face-gaze-target").clip(CircleShape).background(Palette.Primary.copy(alpha = 0.18f)),
                        contentAlignment = Alignment.Center) {
                        Box(Modifier.size(28.dp).clip(CircleShape).background(Palette.Primary))
                    }
                }
                extraOverlay()
            }
        }
    }
}
