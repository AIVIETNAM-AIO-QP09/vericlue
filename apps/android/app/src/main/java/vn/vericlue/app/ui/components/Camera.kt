package vn.vericlue.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.BoxWithConstraintsScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Palette

/**
 * Stand-in for the CameraX preview (APP-02 replaces it). Draws a neutral head-and-shoulders
 * silhouette so the layout reads like a live camera without shipping any real face photo.
 * [faceScale] < 1 shows the person further away ("Lại gần hơn").
 */
@Composable
fun FakeCameraFeed(modifier: Modifier = Modifier, faceScale: Float = 1f, dim: Float = 0f) {
    Canvas(modifier.fillMaxSize()) {
        drawRect(Brush.verticalGradient(listOf(Color(0xFF2A3038), Palette.CameraBg)))
        val cx = size.width / 2f
        val headW = size.width * 0.42f * faceScale
        val headH = headW * 1.3f
        val headTop = size.height * 0.36f - headH / 2f
        val skin = Color(0xFF6B5A50)
        drawOval(
            Brush.radialGradient(listOf(skin, Color(0xFF3E342F)), center = Offset(cx, headTop + headH * 0.45f), radius = headW),
            topLeft = Offset(cx - headW / 2f, headTop),
            size = Size(headW, headH),
        )
        val shoulderTop = headTop + headH * 0.92f
        val shoulderW = headW * 2.4f
        drawOval(
            Color(0xFF1C2733),
            topLeft = Offset(cx - shoulderW / 2f, shoulderTop),
            size = Size(shoulderW, headH * 1.4f),
        )
        if (dim > 0f) drawRect(Color.Black.copy(alpha = dim))
    }
}

/** Geometry of the face oval inside a camera area of the given size. */
fun ovalRect(width: Float, height: Float, density: Float): Rect {
    val w = minOf(250f * density, width * 0.66f)
    val h = w * 1.32f
    val left = (width - w) / 2f
    val top = (height - h) * 0.36f
    return Rect(left, top, left + w, top + h)
}

/**
 * Dark scrim with an oval cut-out. [ringColor] draws the guide; [progress] (0..1) draws the
 * capture ring just outside it.
 */
@Composable
fun OvalOverlay(ringColor: Color, ringWidth: Dp = 2.dp, progress: Float? = null) {
    Canvas(Modifier.fillMaxSize()) {
        val oval = ovalRect(size.width, size.height, density)
        val scrim = Path().apply {
            fillType = PathFillType.EvenOdd
            addRect(Rect(Offset.Zero, size))
            addOval(oval)
        }
        drawPath(scrim, Color(0xD108111A))
        drawOval(ringColor, oval.topLeft, oval.size, style = Stroke(ringWidth.toPx()))
        if (progress != null) {
            val pad = 9.dp.toPx()
            drawArc(
                ringColor,
                startAngle = -90f,
                sweepAngle = 360f * progress,
                useCenter = false,
                topLeft = Offset(oval.left - pad, oval.top - pad),
                size = Size(oval.width + pad * 2, oval.height + pad * 2),
                style = Stroke(3.dp.toPx()),
            )
        }
    }
}

/** Box that exposes the oval position in dp to place chips and arrows around it. */
@Composable
fun CameraArea(modifier: Modifier = Modifier, content: @Composable BoxWithConstraintsScope.(oval: DpRect) -> Unit) {
    BoxWithConstraints(modifier.fillMaxSize()) {
        val w = maxWidth.value
        val h = maxHeight.value
        val r = ovalRect(w, h, 1f)
        content(DpRect(r.left.dp, r.top.dp, r.width.dp, r.height.dp))
    }
}

data class DpRect(val left: Dp, val top: Dp, val width: Dp, val height: Dp) {
    val bottom: Dp get() = top + height
    val centerY: Dp get() = top + height / 2
}

@Composable
fun FullCamera(faceScale: Float = 1f, ringColor: Color = Color.White, progress: Float? = null, ringWidth: Dp = 2.dp) {
    Box(Modifier.fillMaxSize()) {
        CameraFeed(faceScale = faceScale)
        OvalOverlay(ringColor = ringColor, ringWidth = ringWidth, progress = progress)
    }
}

/**
 * Real camera preview when the app provides one (LocalCameraFeed), otherwise the drawn
 * stand-in. Screens call this so previews and screenshot tests still work without a camera.
 */
val LocalCameraFeed = androidx.compose.runtime.staticCompositionLocalOf<(@Composable (Modifier) -> Unit)?> { null }

@Composable
fun CameraFeed(modifier: Modifier = Modifier, faceScale: Float = 1f, dim: Float = 0f) {
    val live = LocalCameraFeed.current
    if (live != null) live(modifier.fillMaxSize()) else FakeCameraFeed(modifier, faceScale, dim)
}

/** The session's single PreviewView, moved into whichever screen is showing it. */
@Composable
fun CameraXPreview(session: vn.vericlue.app.capture.CameraSession, modifier: Modifier = Modifier) {
    androidx.compose.ui.viewinterop.AndroidView(
        factory = { ctx ->
            session.previewView(ctx).also { v -> (v.parent as? android.view.ViewGroup)?.removeView(v) }
        },
        modifier = modifier,
    )
}
