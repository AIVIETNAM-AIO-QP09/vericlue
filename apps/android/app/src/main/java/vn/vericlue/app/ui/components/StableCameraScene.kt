package vn.vericlue.app.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot

data class PreviewTransform(val scale: Float, val x: Float, val y: Float)

/** Fill a preview window without distorting the face or resizing the camera View. */
fun previewTransform(host: Size, window: Rect): PreviewTransform {
    if (host.width <= 0 || host.height <= 0 || window.width <= 0 || window.height <= 0) {
        return PreviewTransform(1f, 0f, 0f)
    }
    return PreviewTransform(
        maxOf(window.width / host.width, window.height / host.height),
        window.center.x - host.width / 2,
        window.center.y - host.height / 2,
    )
}

/**
 * Existing screens keep their CameraFeed cutouts; one underlying PreviewView remains attached
 * and measured at full size throughout the recording. Only its compositor transform changes.
 * Clear belongs to the foreground's offscreen layer, never to the camera surface.
 */
@Composable
fun StableCameraScene(content: @Composable () -> Unit) {
    val feed = LocalCameraFeed.current
    var origin by remember { mutableStateOf(Offset.Zero) }
    var host by remember { mutableStateOf(Size.Zero) }
    var window by remember { mutableStateOf(Rect.Zero) }
    Box(Modifier.fillMaxSize().onGloballyPositioned {
        origin = it.positionInRoot()
        host = Size(it.size.width.toFloat(), it.size.height.toFloat())
    }) {
        Box(Modifier.fillMaxSize().graphicsLayer {
            val transform = previewTransform(host, window)
            scaleX = transform.scale
            scaleY = transform.scale
            translationX = transform.x
            translationY = transform.y
        }) {
            if (feed != null) feed(Modifier.fillMaxSize()) else FakeCameraFeed()
        }
        Box(Modifier.fillMaxSize().graphicsLayer {
            compositingStrategy = CompositingStrategy.Offscreen
        }) {
            CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                Box(modifier.onGloballyPositioned {
                    window = Rect(it.positionInRoot() - origin,
                        Size(it.size.width.toFloat(), it.size.height.toFloat()))
                }.drawBehind { drawRect(Color.Transparent, blendMode = BlendMode.Clear) })
            }) { content() }
        }
    }
}
