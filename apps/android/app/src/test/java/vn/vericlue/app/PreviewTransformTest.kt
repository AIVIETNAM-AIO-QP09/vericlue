package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.ui.components.faceGuideRect
import vn.vericlue.app.ui.components.faceThumbnailRect
import vn.vericlue.app.ui.components.cameraPresentation
import vn.vericlue.app.ui.components.CameraPresentation

class PreviewTransformTest {
    @Test fun guideFitsBetweenReadingAndActionAreas() {
        for (scale in listOf(1f, 2f)) {
            for (density in listOf(1f, 3f)) {
                val r = faceGuideRect(375f * density, 812f * density, density, scale, 24f * density, 24f * density)
                assertEquals(1.32f, r.height / r.width, 0.001f)
                assertEquals(375f * density / 2, r.center.x, 0.01f)
                val minimumTop = (24 + 128 + 64 * scale) * density
                val maximumBottom = (812 - 24 - 112 - 56 * scale) * density
                // Float32 center-minus-half can fall one ULP below the clamp boundary.
                assertTrue("Top ${r.top} must stay above $minimumTop (font=$scale density=$density)", r.top >= minimumTop - .001f)
                assertTrue("Bottom ${r.bottom} must stay below $maximumBottom (font=$scale density=$density)", r.bottom <= maximumBottom + .001f)
            }
        }
    }
    @Test fun shortWindowStillHasAVisibleUndistortedGuide() {
        val r = faceGuideRect(812f, 375f, 1f, 1f, 0f, 0f)
        assertTrue(r.width > 0 && r.height > 0)
        assertTrue(r.left >= 0 && r.right <= 812 && r.top >= 0 && r.bottom <= 375)
        assertEquals(1.32f, r.height / r.width, 0.001f)
    }
    @Test fun normalPhoneGuideIsCompactWhileCameraAcceptanceIsKeptSeparately() {
        val r = faceGuideRect(375f, 812f, 1f, 1f, 24f, 24f)
        assertTrue(r.width >= 375f * 0.60f)
        assertTrue(r.width <= 375f * 0.70f)
    }
    @Test fun thumbnailMapsTheSameFaceAreaAndRestoresTheExactIdentityTransform() {
        val guide = faceGuideRect(375f, 812f, 1f, 1f, 24f, 24f)
        val thumbnail = faceThumbnailRect(375f, 1f, 24f)
        val compact = cameraPresentation(guide, thumbnail, 1f)
        assertEquals(thumbnail.left, guide.left * compact.scale + compact.x, 0.001f)
        assertEquals(thumbnail.top, guide.top * compact.scale + compact.y, 0.001f)
        assertEquals(thumbnail.right, guide.right * compact.scale + compact.x, 0.001f)
        assertEquals(thumbnail.bottom, guide.bottom * compact.scale + compact.y, 0.001f)
        assertEquals(CameraPresentation(), cameraPresentation(guide, thumbnail, 0f))
        assertTrue(compact.scale > 0 && compact.scale < 1)
    }
}
