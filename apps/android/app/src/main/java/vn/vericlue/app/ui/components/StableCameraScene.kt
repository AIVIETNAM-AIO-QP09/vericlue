package vn.vericlue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import kotlin.math.min

/** Drawing coordinates only. The underlying PreviewView retains its full-window layout. */
@Immutable
data class CameraPresentation(val scale: Float = 1f, val x: Float = 0f, val y: Float = 0f)

/** Fits a full native viewport into a thumbnail; rectangles share root coordinates. */
fun fittedCameraPresentation(viewport: Rect, thumbnail: Rect): CameraPresentation {
    val values = listOf(viewport.left, viewport.top, viewport.right, viewport.bottom,
        thumbnail.left, thumbnail.top, thumbnail.right, thumbnail.bottom)
    if (values.any { !it.isFinite() } || viewport.width <= 0f || viewport.height <= 0f ||
        thumbnail.width <= 0f || thumbnail.height <= 0f) return CameraPresentation()
    val scale = min(thumbnail.width / viewport.width, thumbnail.height / viewport.height)
    val x = thumbnail.center.x - viewport.left - viewport.width * scale / 2f
    val y = thumbnail.center.y - viewport.top - viewport.height * scale / 2f
    return if (scale.isFinite() && scale > 0f && x.isFinite() && y.isFinite()) CameraPresentation(scale, x, y)
        else CameraPresentation()
}

fun cameraPresentation(guide: Rect, thumbnail: Rect, progress: Float): CameraPresentation {
    val amount = progress.coerceIn(0f, 1f)
    val targetScale = thumbnail.width / guide.width.coerceAtLeast(1f)
    return CameraPresentation(
        scale = 1f + (targetScale - 1f) * amount,
        x = (thumbnail.left - guide.left * targetScale) * amount,
        y = (thumbnail.top - guide.top * targetScale) * amount,
    )
}

/** One full-window PreviewView. Only its drawing layer moves into the gaze thumbnail. */
@Composable
fun StableCameraScene(
    faceScale: Float = 1f,
    dim: Float = 0f,
    presentation: CameraPresentation = CameraPresentation(),
    content: @Composable () -> Unit,
) {
    val feed = LocalCameraFeed.current
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        Box(Modifier.fillMaxSize().graphicsLayer {
            transformOrigin = TransformOrigin(0f, 0f)
            scaleX = presentation.scale
            scaleY = presentation.scale
            translationX = presentation.x
            translationY = presentation.y
        }) {
            if (feed != null) feed(Modifier.fillMaxSize())
            else FakeCameraFeed(faceScale = faceScale, dim = dim, centerYFraction = 0.5f)
        }
        Box(Modifier.fillMaxSize().graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }) {
            CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                Box(modifier.drawBehind { drawRect(Color.Transparent, blendMode = BlendMode.Clear) })
            }) { content() }
        }
    }
}
