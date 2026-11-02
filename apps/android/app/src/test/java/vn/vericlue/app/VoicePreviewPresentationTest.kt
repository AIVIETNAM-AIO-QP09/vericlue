package vn.vericlue.app

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.ui.components.CameraPresentation
import vn.vericlue.app.ui.components.fittedCameraPresentation

class VoicePreviewPresentationTest {
    @Test fun portraitViewportFitsInsideThumbnailWithoutCuttingOffItsHeadOrFeet() {
        val viewport = Rect(0f, 0f, 375f, 812f)
        val thumbnail = Rect(24f, 180f, 76f, 244f)
        val drawing = fittedCameraPresentation(viewport, thumbnail)
        assertEquals(64f / 812f, drawing.scale, 0.000001f)
        assertFit(viewport, thumbnail, drawing)
    }

    @Test fun commonRootOffsetsDoNotBecomeAnExtraCameraTranslation() {
        val viewport = Rect(30f, 70f, 405f, 882f)
        val thumbnail = Rect(54f, 250f, 106f, 314f)
        assertFit(viewport, thumbnail, fittedCameraPresentation(viewport, thumbnail))
    }

    @Test fun incompleteOrInvalidLayoutCannotCreateANonfiniteDrawingTransform() {
        val valid = Rect(0f, 0f, 100f, 200f)
        for (invalid in listOf(Rect.Zero, Rect(0f, 0f, Float.NaN, 20f), Rect(0f, 0f, 10f, Float.POSITIVE_INFINITY))) {
            assertEquals(CameraPresentation(), fittedCameraPresentation(invalid, valid))
            assertEquals(CameraPresentation(), fittedCameraPresentation(valid, invalid))
        }
    }

    private fun assertFit(viewport: Rect, thumbnail: Rect, drawing: CameraPresentation) {
        fun mapped(point: Offset) = Offset(viewport.left + drawing.x + point.x * drawing.scale,
            viewport.top + drawing.y + point.y * drawing.scale)
        val center = mapped(Offset(viewport.width / 2, viewport.height / 2))
        assertEquals(thumbnail.center.x, center.x, 0.001f)
        assertEquals(thumbnail.center.y, center.y, 0.001f)
        for (corner in listOf(Offset.Zero, Offset(viewport.width, 0f), Offset(0f, viewport.height), Offset(viewport.width, viewport.height))) {
            val at = mapped(corner)
            assertTrue(at.x >= thumbnail.left - .001f && at.x <= thumbnail.right + .001f)
            assertTrue(at.y >= thumbnail.top - .001f && at.y <= thumbnail.bottom + .001f)
        }
    }
}
