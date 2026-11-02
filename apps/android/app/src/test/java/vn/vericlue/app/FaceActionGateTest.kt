package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.TurnDir

class FaceActionGateTest {
    private fun frame(at: Long = 0L, yaw: Float = 0f, identity: Int? = 7) = FaceSignal(
        faces = 1, widthFraction = 0.46f, heightFraction = 0.60f,
        centerX = 0.5f, centerY = 0.48f, yaw = yaw, pitch = 0f, roll = 0f,
        luma = 120f, timestampNs = (at * 1_000_000).coerceAtLeast(1L), observedAtMs = at,
        imageWidth = 480, imageHeight = 640, landmarksComplete = true,
        landmarksVisible = true, trackingId = identity,
    )

    @Test fun partialClippedAndMultipleFacesNeverBecomeReady() {
        assertEquals(FramingState.MultipleFaces, QualityGate.evaluate(frame().copy(faces = 2), 0))
        assertEquals(FramingState.IncompleteFace, QualityGate.evaluate(frame().copy(centerY = 0.15f), 0))
        assertEquals(FramingState.IncompleteFace, QualityGate.evaluate(frame().copy(centerY = 0.85f), 0))
        assertEquals(FramingState.IncompleteFace, QualityGate.evaluate(frame().copy(landmarksComplete = false), 0))
        assertEquals(FramingState.TooClose, QualityGate.evaluate(frame().copy(widthFraction = 0.96f), 0))
    }

    @Test fun readinessRequiresFrontalPoseAndFiniteCompleteGeometry() {
        for (s in listOf(frame(yaw = 20f), frame().copy(pitch = 25f), frame().copy(roll = 20f))) {
            assertEquals(FramingState.NotStraight, QualityGate.evaluate(s, 0))
        }
        for (s in listOf(frame().copy(widthFraction = Float.NaN), frame().copy(heightFraction = 0f), frame().copy(imageWidth = 0))) {
            assertEquals(FramingState.IncompleteFace, QualityGate.evaluate(s, 0))
        }
        assertNotEquals(FramingState.Good, QualityGate.evaluate(FaceSignal(1, .5f, .5f, .5f, 0f, 120f, 0), 0))
    }

    @Test fun staleAndFutureSignalsNeverCountAsCurrentFaces() {
        assertEquals(FramingState.NoFace, QualityGate.evaluate(frame(), 501))
        assertEquals(FramingState.NoFace, QualityGate.evaluate(frame(at = 200), 100))
        assertFalse(QualityGate.hasCompleteFace(frame(), 501))
    }

    @Test fun delayedSensorFramesCannotBecomeFreshAtAnalyzerReceipt() {
        val delayed = frame(1000).copy(observedAtMs = 2000)
        assertFalse(QualityGate.isFresh(delayed, 2000))
        assertEquals(FramingState.NoFace, QualityGate.evaluate(delayed, 2000))
        val gate = HeadActionGate(TurnDir.Left)
        for (at in 2000L..3000L step 100) {
            assertFalse(gate.update(frame(at - 1000, 26f).copy(observedAtMs = at), at))
        }
        assertFalse(gate.complete)
        for (stamp in listOf(0L, -1L)) {
            assertFalse(QualityGate.isFresh(frame(2000).copy(timestampNs = stamp), 2000))
        }
    }

    @Test fun analyzerDeliveryJitterCannotInflateTheMeasuredPoseHold() {
        val gate = HeadActionGate(TurnDir.Left, holdMs = 350)
        // Delivery spans 400ms, but the camera only observed the pose for 200ms.
        assertFalse(gate.update(frame(1000, 26f), 1000))
        assertFalse(gate.update(frame(1100, 26f).copy(observedAtMs = 1200), 1200))
        assertFalse(gate.update(frame(1200, 26f).copy(observedAtMs = 1400), 1400))
        assertTrue(gate.progress < 1f)
        assertTrue(gate.update(frame(1350, 26f).copy(observedAtMs = 1500), 1500))
    }

    @Test fun queuedFrameFromBeforeJpegRequestDoesNotCountAsNewCapture() {
        val queued = frame(1000).copy(observedAtMs = 1100)
        assertTrue(QualityGate.isFresh(queued, 1200))
        assertFalse(QualityGate.isFresh(queued, 1200, capturedAfterMs = 1050))
        assertTrue(QualityGate.isFresh(frame(1100), 1200, capturedAfterMs = 1050))
    }

    @Test fun readinessNeedsASecondOfDistinctFramesInsideGuide() {
        val gate = StableFaceGate()
        for (t in 0L..800L step 200) assertFalse(gate.update(frame(t), t))
        assertTrue(gate.update(frame(1000), 1000))
        assertEquals(1f, gate.progress, 0f)
        assertFalse(gate.update(frame(1100), 1100, insideGuide = false))
        assertEquals(0f, gate.progress, 0f)
        assertFalse(gate.update(frame(1200), 1200))
    }

    @Test fun repeatedUiPollingCannotCompleteAStalledCamera() {
        val gate = StableFaceGate()
        val single = frame()
        for (t in 0L..1600L step 50) assertFalse(gate.update(single, t))
        assertEquals(0f, gate.progress, 0f)
    }

    @Test fun gapInvalidPoseAndDifferentTrackingIdResetReadiness() {
        val gate = StableFaceGate()
        for (t in 0L..800L step 200) gate.update(frame(t), t)
        assertFalse(gate.update(frame(1000, identity = 8), 1000))
        assertFalse(gate.update(frame(1800, identity = 8), 1800))
        assertFalse(gate.update(frame(2000, yaw = 30f, identity = 8), 2000))
        assertEquals(0f, gate.progress, 0f)
        assertFalse(gate.update(frame(2200, identity = 8), 2200))
    }

    @Test fun leftAndRightRequireTheRequestedSignedYaw() {
        for ((direction, correct) in listOf(TurnDir.Left to 26f, TurnDir.Right to -26f)) {
            val gate = HeadActionGate(direction)
            for (t in 0L..700L step 175) assertFalse(gate.update(frame(t, -correct), t))
            assertFalse(gate.update(frame(800, correct), 800))
            assertFalse(gate.update(frame(975, correct), 975))
            assertTrue(gate.update(frame(1150, correct), 1150))
            assertTrue(gate.complete)
            gate.reset()
            assertFalse(gate.complete)
            assertFalse(gate.update(frame(1400, correct), 1400))
        }
    }

    @Test fun stillHeadAndSingleTurnSampleCannotCompleteTurn() {
        val gate = HeadActionGate(TurnDir.Left)
        for (t in 0L..1000L step 100) assertFalse(gate.update(frame(t), t))
        val oneTurn = frame(1100, 26f)
        for (t in 1100L..1700L step 50) assertFalse(gate.update(oneTurn, t))
        assertFalse(gate.complete)
    }

    @Test fun centerRequiresItsOwnHoldAndFreshSamples() {
        val gate = HeadActionGate(null)
        for (t in 0L..700L step 175) assertFalse(gate.update(frame(t, 30f), t))
        assertFalse(gate.update(frame(800), 800))
        assertFalse(gate.update(frame(1000), 1000))
        assertTrue(gate.update(frame(1200), 1200))
    }

    @Test fun occlusionDuringTurnResetsButFarEyeMayDisappearInSidePose() {
        val gate = HeadActionGate(TurnDir.Left)
        gate.update(frame(0, 26f), 0)
        gate.update(frame(175, 26f), 175)
        assertFalse(gate.update(frame(350, 26f).copy(landmarksVisible = false), 350))
        assertFalse(gate.update(frame(500, 28f).copy(landmarksComplete = false), 500))
        assertFalse(gate.update(frame(675, 28f).copy(landmarksComplete = false), 675))
        assertTrue(gate.update(frame(850, 28f).copy(landmarksComplete = false), 850))
    }

    @Test fun legacyTrackerAlsoRejectsTheOppositeDirection() {
        val gate = TurnTracker(direction = TurnDir.Right)
        for (t in 0L..1000L step 100) gate.update(30f, t)
        assertFalse(gate.turned)
        assertFalse(gate.update(0f, 1100))
    }

    @Test fun sidePoseMayNarrowWithoutRequiringPhoneRepositioning() {
        val narrow = frame(yaw = 35f).copy(widthFraction = 0.26f)
        assertTrue(QualityGate.hasCompleteFace(narrow, 0))
        assertNotEquals(FramingState.Good, QualityGate.evaluate(narrow, 0))
    }
}
