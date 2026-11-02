package vn.vericlue.app

import androidx.compose.ui.geometry.Rect
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.FramingState

class FramingAlignmentTest {
    private val guide = Rect(0f, 0f, 100f, 140f)
    private val centered = Rect(5f, 7f, 95f, 133f)
    private fun frame(at: Long = 0L, width: Float = .28f) = FaceSignal(
        faces = 1, widthFraction = width, heightFraction = .36f,
        centerX = .5f, centerY = .48f, yaw = 0f, pitch = 0f, roll = 0f,
        luma = 120f, timestampNs = at * 1_000_000, observedAtMs = at,
        imageWidth = 480, imageHeight = 640, landmarksComplete = true,
        landmarksVisible = true, trackingId = 7,
    )

    @Test fun clearFaceAtNaturalDistanceDoesNotNeedToFillThirtyTwoPercentOfImage() {
        for (width in listOf(.24f, .28f, .32f, .45f, .65f)) {
            assertEquals(FramingState.Good, QualityGate.evaluate(frame(width = width), 0))
        }
        assertEquals(FramingState.TooFar, QualityGate.evaluate(frame(width = .20f), 0))
        assertEquals(FramingState.TooFar, QualityGate.evaluate(frame().copy(imageWidth = 320), 0))
        assertEquals(FramingState.TooFar, QualityGate.evaluate(frame().copy(heightFraction = .12f), 0))
    }

    @Test fun lowerDistanceRequirementNeverAcceptsPartialMultipleOrStaleFaces() {
        for (partial in listOf(frame().copy(centerY = .08f), frame().copy(landmarksComplete = false), frame().copy(faces = 2))) {
            assertNotEquals(FramingState.Good, QualityGate.evaluate(partial, 0))
        }
        assertEquals(FramingState.NoFace, QualityGate.evaluate(frame(), 501))
    }

    @Test fun outlineToleranceAcceptsSmallDetectorJitterButNotFaceOutsideFrame() {
        val touchingOutline = Rect(0f, 0f, 100f, 140f)
        val smallJitter = Rect(-2f, -2.8f, 102f, 142.8f)
        assertTrue(faceFitsGuide(touchingOutline, guide))
        assertTrue(faceFitsGuide(smallJitter, guide))
        assertFalse(faceFitsGuide(Rect(-10f, -14f, 110f, 154f), guide))
        val gate = FramingAlignmentGate()
        val feedback = gate.update(frame().copy(centerY = .05f), 0, smallJitter, guide)
        assertEquals(FramingState.IncompleteFace, feedback.state)
        assertFalse(feedback.ready)
    }

    @Test fun guidanceSeparatesDistanceFromPositionAndUnavailableMapping() {
        assertEquals(GuideAlignment.TooClose, faceGuideAlignment(Rect(-10f, -14f, 110f, 154f), guide))
        assertEquals(GuideAlignment.OffCenter, faceGuideAlignment(Rect(70f, 45f, 110f, 95f), guide))
        assertEquals(GuideAlignment.Unavailable, faceGuideAlignment(null, guide))
        assertEquals(GuideAlignment.Unavailable, faceGuideAlignment(centered, Rect.Zero))
        assertEquals(GuideAlignment.Unavailable, faceGuideAlignment(Rect(Float.NaN, 0f, 50f, 50f), guide))
        val gate = FramingAlignmentGate()
        val waiting = gate.update(frame(), 0, null, guide)
        assertTrue(waiting.preparingCamera)
        assertFalse(waiting.ready)
        assertEquals(0f, waiting.progress, 0f)
        assertEquals(FramingState.OffCenter, gate.update(frame(100), 100, Rect(70f, 45f, 110f, 95f), guide).state)
        assertEquals(FramingState.TooClose, gate.update(frame(200), 200, Rect(-10f, -14f, 110f, 154f), guide).state)
    }

    @Test fun boundedHysteresisPreventsDistanceHintsAlternatingDuringStableHold() {
        val gate = FramingAlignmentGate()
        val jitter = Rect(-4f, -5.6f, 104f, 145.6f)
        assertEquals(GuideAlignment.TooClose, faceGuideAlignment(jitter, guide))
        assertFalse(gate.update(frame(), 0, centered, guide).ready)
        for (at in 200L..800L step 200) {
            val feedback = gate.update(frame(at), at, jitter, guide)
            assertEquals(FramingState.Good, feedback.state)
            assertFalse(feedback.ready)
            assertTrue(feedback.progress > 0f)
        }
        val ready = gate.update(frame(1000), 1000, jitter, guide)
        assertTrue(ready.ready)
        assertTrue(gate.acceptsLatest(frame(1050), 1050, jitter, guide))
        assertFalse(gate.acceptsLatest(frame(1050).copy(landmarksComplete = false), 1050, jitter, guide))
        gate.reset()
        assertEquals(FramingState.TooClose, gate.update(frame(1200), 1200, jitter, guide).state)
    }

    @Test fun realLossImmediatelyClearsProgressInsteadOfKeepingAFullRing() {
        val gate = FramingAlignmentGate()
        for (at in 0L..800L step 200) gate.update(frame(at), at, centered, guide)
        val lost = gate.update(frame(1000).copy(landmarksComplete = false), 1000, centered, guide)
        assertEquals(0f, lost.progress, 0f)
        assertFalse(lost.ready)
        val firstAgain = gate.update(frame(1200), 1200, centered, guide)
        assertEquals(0f, firstAgain.progress, 0f)
        assertFalse(firstAgain.ready)
        val missingTransform = gate.update(frame(1400), 1400, null, guide)
        assertTrue(missingTransform.preparingCamera)
        assertEquals(0f, missingTransform.progress, 0f)
    }

    @Test fun alignmentToleranceCannotTurnRepeatedOrOldSamplesIntoCapture() {
        val gate = FramingAlignmentGate()
        val old = frame()
        for (at in 0L..1000L step 50) {
            val feedback = gate.update(old, at, centered, guide)
            assertFalse(feedback.ready)
            assertEquals(0f, feedback.progress, 0f)
        }
    }
}
