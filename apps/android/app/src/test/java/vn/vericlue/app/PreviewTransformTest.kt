package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.ui.components.faceGuideRect

class PreviewTransformTest {
    @Test fun guideFitsBetweenReadingAndActionAreas() {
        for (scale in listOf(1f, 2f)) {
            for (density in listOf(1f, 3f)) {
                val r = faceGuideRect(375f * density, 812f * density, density, scale, 24f * density, 24f * density)
                assertEquals(1.32f, r.height / r.width, 0.001f)
                assertEquals(375f * density / 2, r.center.x, 0.01f)
                assertTrue(r.top >= (24 + 128 + 32 * scale) * density)
                assertTrue(r.bottom <= (812 - 24 - 84 - 32 * scale) * density)
            }
        }
    }
    @Test fun shortWindowStillHasAVisibleUndistortedGuide() {
        val r = faceGuideRect(812f, 375f, 1f, 1f, 0f, 0f)
        assertTrue(r.width > 0 && r.height > 0)
        assertTrue(r.left >= 0 && r.right <= 812 && r.top >= 0 && r.bottom <= 375)
        assertEquals(1.32f, r.height / r.width, 0.001f)
    }
}
