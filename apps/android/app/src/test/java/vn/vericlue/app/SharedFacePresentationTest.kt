package vn.vericlue.app

import androidx.compose.ui.geometry.Rect
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.GuideAlignment
import vn.vericlue.app.capture.FaceSignal
import vn.vericlue.app.capture.FramingAlignmentGate
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.capture.faceGuideAlignment
import vn.vericlue.app.ui.components.*

class SharedFacePresentationTest {
    @Test fun compactDisplayDoesNotRequireASmallerFaceAtLargerTextSizes() {
        for ((width, height) in listOf(375f to 812f, 360f to 640f, 412f to 915f)) {
            val source = faceSourceGuideRect(width, height, 1f, 24f, 24f)
            val face = Rect(source.left + source.width * .05f, source.top + source.height * .05f,
                source.right - source.width * .05f, source.bottom - source.height * .05f)
            assertEquals(GuideAlignment.Good, faceGuideAlignment(face, source))
            for (fontScale in listOf(1f, 1.5f, 2f)) {
                val display = faceGuideRect(width, height, 1f, fontScale, 24f, 24f)
                val thumbnail = faceThumbnailRect(width, 1f, 24f)
                assertTrue("Compact oval should be smaller than the accepted camera region", display.width < source.width)
                for (phaseProgress in listOf(0f, .5f, 1f)) {
                    val drawing = faceCameraPresentation(source, display, thumbnail, phaseProgress)
                    assertEquals(GuideAlignment.Good, faceGuideAlignment(mapped(face, drawing), mapped(source, drawing)))
                    val oversized = Rect(source.left - source.width * .1f, source.top - source.height * .1f,
                        source.right + source.width * .1f, source.bottom + source.height * .1f)
                    assertEquals(GuideAlignment.TooClose, faceGuideAlignment(mapped(oversized, drawing), mapped(source, drawing)))
                }
            }
        }
    }

    @Test fun establishedNormalFontSourceBoundsArePreservedInCameraCoordinates() {
        // Normal-font reserved areas: top216 + bottom192 leaves404px of height.
        val source = faceSourceGuideRect(375f, 812f, 1f, 24f, 24f)
        assertEquals(306.0606f, source.width, .01f)
        assertEquals(404f, source.height, .01f)
        assertEquals(216f, source.top, .01f)
        assertEquals(34.4697f, source.left, .01f)
    }

    @Test fun syntheticFitPreviewCoordinatesMapTheSameFaceAcrossDisplayModes() {
        // 480x640 upright analysis in a 375x812 FIT host: scale .78125, y letterbox 156.
        val source = faceSourceGuideRect(375f, 812f, 1f, 24f, 24f)
        val face = Rect(72f * .78125f, 116f * .78125f + 156f,
            408f * .78125f, 564f * .78125f + 156f)
        val offCenter = face.translate(androidx.compose.ui.geometry.Offset(110f, 0f))
        for (target in listOf(faceGuideRect(375f, 812f, 1f, 2f, 24f, 24f),
            faceThumbnailRect(375f, 1f, 24f), Rect(20f, 120f, 92f, 215.04f))) {
            val drawing = cameraPresentation(source, target, 1f)
            assertEquals(GuideAlignment.Good, faceGuideAlignment(mapped(face, drawing), mapped(source, drawing)))
            assertEquals(GuideAlignment.OffCenter, faceGuideAlignment(mapped(offCenter, drawing), mapped(source, drawing)))
            assertEquals(target.center.x, mapped(source, drawing).center.x, .001f)
            assertEquals(target.center.y, mapped(source, drawing).center.y, .001f)
        }
    }

    @Test fun sourceGuideNeverChangesWithPresentationOrRootOffsets() {
        val source = faceSourceGuideRect(375f, 812f, 1f, 24f, 24f)
        val viewport = Rect(30f, 70f, 405f, 882f)
        val thumbnail = Rect(54f, 250f, 126f, 345.04f)
        val drawing = voiceFacePresentation(viewport, thumbnail, 1f, 24f, 24f)
        val actual = mapped(source, drawing).translate(viewport.topLeft)
        assertEquals(thumbnail.left, actual.left, .001f)
        assertEquals(thumbnail.top, actual.top, .001f)
        assertEquals(thumbnail.right, actual.right, .001f)
        assertEquals(thumbnail.bottom, actual.bottom, .001f)
    }

    @Test fun voiceWaitsForFiniteNonemptyBoundsBeforeTransformingTheNativePreview() {
        val valid = Rect(0f, 0f, 375f, 812f)
        for (invalid in listOf(Rect.Zero, Rect(0f, 0f, Float.NaN, 20f),
            Rect(0f, 0f, 20f, Float.POSITIVE_INFINITY))) {
            assertEquals(CameraPresentation(), voiceFacePresentation(invalid, valid, 1f, 24f, 24f))
            assertEquals(CameraPresentation(), voiceFacePresentation(valid, invalid, 1f, 24f, 24f))
        }
    }

    @Test fun minimumFillGuidanceIsTheSameAtEveryFontSizeAndDisplayPhase() {
        val signal = FaceSignal(1, .4f, .5f, .5f, 0f, 120f, 1L,
            heightFraction = .5f, imageWidth = 480, imageHeight = 640,
            pitch = 0f, roll = 0f, landmarksComplete = true, landmarksVisible = true,
            observedAtMs = 0, trackingId = 7)
        val source = faceSourceGuideRect(375f, 812f, 1f, 24f, 24f)
        val small = Rect(source.left + source.width * .18f, source.top + source.height * .1f,
            source.right - source.width * .18f, source.bottom - source.height * .1f)
        val filled = Rect(source.left + source.width * .1f, source.top + source.height * .1f,
            source.right - source.width * .1f, source.bottom - source.height * .1f)
        for (fontScale in listOf(1f, 1.5f, 2f)) {
            val display = faceGuideRect(375f, 812f, 1f, fontScale, 24f, 24f)
            for (progress in listOf(0f, .5f, 1f)) {
                val drawing = faceCameraPresentation(source, display, faceThumbnailRect(375f, 1f, 24f), progress)
                val gate = FramingAlignmentGate()
                assertEquals(FramingState.TooFar,
                    gate.update(signal, 0, mapped(small, drawing), mapped(source, drawing)).state)
                assertEquals(FramingState.Good,
                    gate.update(signal, 0, mapped(filled, drawing), mapped(source, drawing)).state)
            }
        }
    }

    private fun mapped(rect: Rect, drawing: CameraPresentation) = Rect(
        rect.left * drawing.scale + drawing.x, rect.top * drawing.scale + drawing.y,
        rect.right * drawing.scale + drawing.x, rect.bottom * drawing.scale + drawing.y,
    )
}
