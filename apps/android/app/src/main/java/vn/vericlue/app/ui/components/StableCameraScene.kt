package vn.vericlue.app.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer

/** One full-window PreviewView. Foreground cutouts never scale, translate or remeasure it. */
@Composable
fun StableCameraScene(faceScale: Float = 1f, dim: Float = 0f, content: @Composable () -> Unit) {
    val feed = LocalCameraFeed.current
    Box(Modifier.fillMaxSize()) {
        if (feed != null) feed(Modifier.fillMaxSize()) else FakeCameraFeed(faceScale = faceScale, dim = dim)
        Box(Modifier.fillMaxSize().graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }) {
            CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                Box(modifier.drawBehind { drawRect(Color.Transparent, blendMode = BlendMode.Clear) })
            }) { content() }
        }
    }
}
