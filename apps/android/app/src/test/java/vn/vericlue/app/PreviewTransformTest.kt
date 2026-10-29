package vn.vericlue.app

import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.ui.components.previewTransform

class PreviewTransformTest {
    @Test fun fillsEachWindowWithoutStretchingTheFace() {
        val host = Size(400f, 800f)
        for (window in listOf(Rect(114f, 170f, 286f, 398f), Rect(288f, 130f, 384f, 258f), Rect(0f, 100f, 400f, 780f))) {
            val t = previewTransform(host, window)
            val w = host.width * t.scale
            val h = host.height * t.scale
            assertTrue(w >= window.width && h >= window.height)
            assertEquals(host.width / host.height, w / h, 0.0001f)
            assertEquals(window.center.x, host.width / 2 + t.x, 0.0001f)
            assertEquals(window.center.y, host.height / 2 + t.y, 0.0001f)
        }
    }

    @Test fun unmeasuredPreviewIsNotScaledToZero() {
        assertEquals(1f, previewTransform(Size.Zero, Rect.Zero).scale, 0f)
    }
}
