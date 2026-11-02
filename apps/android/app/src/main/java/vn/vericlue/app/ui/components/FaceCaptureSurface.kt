package vn.vericlue.app.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

/** Phase-independent full-window guide. Reserve the same reading/action space in every phase. */
fun faceGuideRect(width: Float, height: Float, density: Float, fontScale: Float, topInset: Float, bottomInset: Float): Rect {
    val top = topInset + (128f + 64f * fontScale) * density
    val bottom = bottomInset + (112f + 56f * fontScale) * density
    val available = (height - top - bottom).coerceAtLeast(24f * density)
    val h = minOf(minOf(320f * density, width * 0.82f) * 1.32f, available)
    val w = h / 1.32f
    val center = (height * 0.46f).coerceIn(top + h / 2, maxOf(top + h / 2, height - bottom - h / 2))
    return Rect((width - w) / 2, center - h / 2, (width + w) / 2, center + h / 2)
}

fun faceThumbnailRect(width: Float, density: Float, topInset: Float): Rect {
    val w = minOf(92f * density, width * 0.24f)
    val right = width - 20f * density
    val top = topInset + 112f * density
    return Rect(right - w, top, right, top + w * 1.32f)
}

/** CameraX keeps one full-size host; gaze changes only its visual presentation, never capture. */
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
    onGuidePosition: ((Rect, Size) -> Unit)? = null,
    actionProgress: Float? = null,
    headGuidance: Boolean = false,
    extraOverlay: @Composable () -> Unit = {},
) {
    BackHandler(onBack = onStop)
    VcTheme(dark = !light) {
        SystemBarIcons(background)
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val density = LocalDensity.current
            val motion = Vc.motion
            val top = WindowInsets.statusBars.getTop(density).toFloat()
            val bottom = WindowInsets.navigationBars.getBottom(density).toFloat()
            val viewport = Size(constraints.maxWidth.toFloat(), constraints.maxHeight.toFloat())
            val oval = faceGuideRect(viewport.width, viewport.height, density.density, density.fontScale, top, bottom)
            val thumbnail = faceThumbnailRect(viewport.width, density.density, top)
            val reportGuide by rememberUpdatedState(onGuidePosition)
            val compact by animateFloatAsState(
                if (gaze != null) 1f else 0f,
                tween(motion.duration(360), easing = FastOutSlowInEasing), label = "camera-thumbnail",
            )
            val drawing = cameraPresentation(oval, thumbnail, compact)
            val aperture = Rect(
                oval.left * drawing.scale + drawing.x, oval.top * drawing.scale + drawing.y,
                oval.right * drawing.scale + drawing.x, oval.bottom * drawing.scale + drawing.y,
            )
            val radius = CornerRadius(
                aperture.width / 2f * (1f - compact) + 16f * density.density * compact,
                aperture.height / 2f * (1f - compact) + 16f * density.density * compact,
            )
            val ink = if (light) Palette.Ink else Color.White
            val ring = if (good) Palette.OkOnDark else if (light) Palette.Primary else Color.White
            StableCameraScene(faceScale = faceScale, dim = dim, presentation = drawing) {
                CameraFeed(Modifier.fillMaxSize())
                Canvas(Modifier.fillMaxSize()) {
                    val mask = Path().apply {
                        fillType = PathFillType.EvenOdd
                        addRect(Rect(Offset.Zero, size))
                        addRoundRect(RoundRect(aperture, radius))
                    }
                    drawPath(mask, background)
                }
                Canvas(Modifier.offset(x = with(density) { aperture.left.toDp() }, y = with(density) { aperture.top.toDp() })
                    .size(with(density) { aperture.width.toDp() }, with(density) { aperture.height.toDp() })
                    .onGloballyPositioned { reportGuide?.invoke(oval, viewport) }
                    .testTag(if (gaze == null) "face-guide" else "face-preview-thumbnail")) {
                    drawRoundRect(ring, cornerRadius = radius, style = Stroke(2.dp.toPx()))
                    if (gaze == null) (actionProgress ?: progress)?.let {
                        val pad = 7.dp.toPx()
                        drawArc(ring, -90f, 360 * it.coerceIn(0f, 1f), false,
                            Offset(-pad, -pad), Size(size.width + 2 * pad, size.height + 2 * pad), style = Stroke(3.dp.toPx()))
                    }
                }
                Column(Modifier.fillMaxWidth().statusBarsPadding().testTag("face-instruction-header")) {
                    TopBar(onStop)
                    StepProgress(2, stepLabel(2))
                    Text(title, style = VcType.titleMedium, color = ink,
                        textAlign = if (gaze == null) TextAlign.Center else TextAlign.Start,
                        modifier = Modifier.fillMaxWidth().padding(start = 20.dp, top = 12.dp, bottom = 12.dp,
                            end = if (gaze == null) 20.dp else with(density) { thumbnail.width.toDp() } + 36.dp))
                }
                Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding()
                    .padding(horizontal = 24.dp, vertical = 12.dp).testTag("face-action-footer"), verticalArrangement = Arrangement.spacedBy(12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        if (headGuidance) HeadMotionGuide(direction, actionProgress ?: 0f, Modifier.size(96.dp, 56.dp))
                        Text(hint, style = VcType.bodySmall, color = ink,
                            textAlign = if (headGuidance) TextAlign.Start else TextAlign.Center,
                            modifier = Modifier.weight(1f))
                    }
                    SecondaryButton("Dừng xác minh", onStop)
                }
                // The target follows server coordinates exactly; no easing, lag, or independent pulse.
                gaze?.let {
                    Canvas(Modifier.offset(maxWidth * it.x - 28.dp, maxHeight * it.y - 28.dp).size(56.dp)
                        .testTag("face-gaze-target")) {
                        drawCircle(Palette.Primary.copy(alpha = 0.13f))
                        drawCircle(Color.White, radius = 18.dp.toPx())
                        drawCircle(Palette.ButtonNavy, radius = 17.dp.toPx(), style = Stroke(3.dp.toPx()))
                        drawCircle(Palette.Primary, radius = 11.dp.toPx())
                        drawCircle(Color.White, radius = 3.dp.toPx())
                    }
                }
                extraOverlay()
            }
        }
    }
}
