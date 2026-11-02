package vn.vericlue.app

import androidx.compose.ui.geometry.Rect
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.TurnDir

class FaceAttemptGuardTest {
    private fun timeline(adaptive: Boolean = true) = FaceTimeline(
        listOf(ColorSlot(null, "#d1d1d1", 1000)), 500, emptyList(),
        listOf(TurnDir.Left, TurnDir.Right, null), 1000, 6000, if (adaptive) 29000 else null,
    )

    private fun frame(at: Long, yaw: Float = 0f, id: Int? = 7) = FaceSignal(
        faces = 1, widthFraction = .46f, heightFraction = .60f, centerX = .5f, centerY = .48f,
        yaw = yaw, pitch = 0f, roll = 0f, luma = 120f, timestampNs = (at * 1_000_000).coerceAtLeast(1L),
        observedAtMs = at, imageWidth = 480, imageHeight = 640,
        landmarksComplete = true, landmarksVisible = true, trackingId = id,
    )

    private fun complete(guard: FaceAttemptGuard, segment: Int, direction: TurnDir?, start: Long) {
        val yaw = when (direction) { TurnDir.Left -> 30f; TurnDir.Right -> -30f; null -> 0f }
        for (at in listOf(start, start + 175, start + 350)) {
            assertNull(guard.update(FaceTimeline.Phase.Head(segment, direction), frame(at, yaw), at))
        }
        assertEquals(1f, guard.actionProgress, 0f)
    }

    @Test fun legacyTimedGuidanceDoesNotGainAnAdaptiveActionCompletionGate() {
        val guard = FaceAttemptGuard(timeline(adaptive = false))
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(1), 1))
        for ((segment, yaw) in listOf(0 to 20f, 1 to -20f, 2 to 0f)) {
            val direction = when (segment) { 0 -> TurnDir.Left; 1 -> TurnDir.Right; else -> null }
            for (at in (1000L + segment * 2000L)..(2700L + segment * 2000L) step 100) {
                assertNull(guard.update(FaceTimeline.Phase.Head(segment, direction), frame(at, yaw), at))
            }
        }
        assertNull(guard.update(FaceTimeline.Phase.Done, frame(7000), 7000))
    }

    @Test fun requestedLeftRightAndCenterCompleteOnlyAfterEachObservedHold() {
        val guard = FaceAttemptGuard(timeline())
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
        complete(guard, 0, TurnDir.Left, 1000)
        complete(guard, 1, TurnDir.Right, 3000)
        complete(guard, 2, null, 5000)
        assertNull(guard.update(FaceTimeline.Phase.Done, frame(7000), 7000))
    }

    @Test fun stillHeadCannotAdvanceToTheNextRequestedDirection() {
        val guard = FaceAttemptGuard(timeline())
        for (at in 1000L..2800L step 200) {
            assertNull(guard.update(FaceTimeline.Phase.Head(0, TurnDir.Left), frame(at), at))
        }
        assertEquals(FaceAttemptIssue.ActionIncomplete,
            guard.update(FaceTimeline.Phase.Head(1, TurnDir.Right), frame(3000), 3000))
        assertEquals(FaceAttemptIssue.ActionIncomplete,
            guard.update(FaceTimeline.Phase.Head(0, TurnDir.Left), frame(3200, 30f), 3200))
    }

    @Test fun oppositeDirectionDoesNotSatisfyTheCurrentInstruction() {
        val guard = FaceAttemptGuard(timeline())
        for (at in 1000L..2800L step 200) {
            assertNull(guard.update(FaceTimeline.Phase.Head(0, TurnDir.Left), frame(at, -30f), at))
        }
        assertEquals(FaceAttemptIssue.ActionIncomplete,
            guard.update(FaceTimeline.Phase.Head(1, TurnDir.Right), frame(3000, -30f), 3000))
    }

    @Test fun missingCenterIsNotAnAutomaticallyCompletedFinalStep() {
        val guard = FaceAttemptGuard(timeline())
        complete(guard, 0, TurnDir.Left, 1000)
        complete(guard, 1, TurnDir.Right, 3000)
        for (at in 5000L..6800L step 200) {
            assertNull(guard.update(FaceTimeline.Phase.Head(2, null), frame(at, -30f), at))
        }
        assertEquals(FaceAttemptIssue.ActionIncomplete, guard.update(FaceTimeline.Phase.Done, frame(7000), 7000))
    }

    @Test fun staleCameraFailsAfterGraceEvenWithoutNewStateFlowEmission() {
        val guard = FaceAttemptGuard(timeline())
        val old = frame(0)
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), old, 0))
        assertNull(guard.update(FaceTimeline.Phase.Gap, old, 600))
        assertNull(guard.update(FaceTimeline.Phase.Gap, old, 1049))
        assertEquals(FaceAttemptIssue.FaceLost, guard.update(FaceTimeline.Phase.Gap, old, 1050))
    }

    @Test fun partialFaceAndNoFaceCannotFinishDuringGrace() {
        for (partial in listOf<FaceSignal?>(null, frame(100).copy(landmarksVisible = false), frame(100).copy(centerY = .15f))) {
            val guard = FaceAttemptGuard(FaceTimeline.passive())
            assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
            assertNull(guard.update(FaceTimeline.Phase.Colour(0), partial, 100))
            assertEquals(FaceAttemptIssue.FaceLost, guard.update(FaceTimeline.Phase.Done, partial, 200))
        }
    }

    @Test fun briefDetectionDropoutMayRecoverButLongerLossIsLatched() {
        val guard = FaceAttemptGuard(timeline())
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), null, 0))
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(300), 300))
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), null, 400))
        assertEquals(FaceAttemptIssue.FaceLost, guard.update(FaceTimeline.Phase.Colour(0), null, 850))
        assertEquals(FaceAttemptIssue.FaceLost, guard.update(FaceTimeline.Phase.Colour(0), frame(900), 900))
    }

    @Test fun skippedOrWronglyLabelledSegmentCannotSupplyTheRequiredEvidence() {
        val skipped = FaceAttemptGuard(timeline())
        complete(skipped, 0, TurnDir.Left, 1000)
        assertEquals(FaceAttemptIssue.ActionIncomplete,
            skipped.update(FaceTimeline.Phase.Head(2, null), frame(5000), 5000))
        for (phase in listOf(FaceTimeline.Phase.Head(0, TurnDir.Right), FaceTimeline.Phase.Head(-1, TurnDir.Left), FaceTimeline.Phase.Head(3, null))) {
            assertEquals(FaceAttemptIssue.ActionIncomplete, FaceAttemptGuard(timeline()).update(phase, frame(1000), 1000))
        }
    }

    @Test fun changedOrMissingEstablishedTrackingIdInvalidatesAttempt() {
        for (id in listOf(8, null)) {
            val guard = FaceAttemptGuard(timeline())
            assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
            assertEquals(FaceAttemptIssue.FaceLost, guard.update(FaceTimeline.Phase.Colour(0), frame(200, id = id), 200))
        }
    }

    @Test fun passiveCaptureStillRequiresCurrentCompleteFaceAtCompletion() {
        val guard = FaceAttemptGuard(FaceTimeline.passive())
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
        assertNull(guard.update(FaceTimeline.Phase.Done, frame(3000), 3000))
        val missing = FaceAttemptGuard(timeline())
        assertEquals(FaceAttemptIssue.ActionIncomplete, missing.update(FaceTimeline.Phase.Done, frame(7000), 7000))
    }

    @Test fun wholeFaceEllipseMustFitGuideNotOnlyItsCenter() {
        val guide = Rect(0f, 0f, 100f, 140f)
        assertTrue(faceFitsGuide(Rect(15f, 20f, 85f, 120f), guide))
        assertFalse(faceFitsGuide(Rect(-10f, 20f, 110f, 120f), guide))
        assertFalse(faceFitsGuide(Rect(15f, -20f, 85f, 100f), guide))
        assertFalse(faceFitsGuide(Rect(15f, 40f, 85f, 160f), guide))
        assertFalse(faceFitsGuide(Rect(75f, 45f, 115f, 95f), guide))
        assertFalse(faceFitsGuide(null, guide))
        assertFalse(faceFitsGuide(Rect.Zero, guide))
        assertFalse(faceFitsGuide(Rect(Float.NaN, 0f, 50f, 50f), guide))
    }

    @Test fun adaptiveControllerAndGuardKeepWrongTurnInlineThenFinishTogether() {
        val plan = timeline(adaptive = true)
        val guard = FaceAttemptGuard(plan)
        val controller = AdaptiveHeadCapture(plan.headTurns, plan.headDeadlineMs.toDouble())
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
        var done = false
        for (at in 1000L..10000L step 100) {
            val yaw = when {
                at < 5000 -> -30f // wrong first direction for several former timed slots
                at < 6100 -> 30f
                at < 7300 -> -30f
                else -> 0f
            }
            val signal = frame(at, yaw)
            val state = controller.update(signal, at, at.toDouble())
            assertNull(state.issue)
            val phase = if (state.done) FaceTimeline.Phase.Done else FaceTimeline.Phase.Head(state.segment, state.direction)
            assertNull(guard.update(phase, signal, at))
            if (at < 5000) assertEquals(0, state.segment)
            if (state.done) { done = true; break }
        }
        assertTrue(done)
    }

    @Test fun adaptivePoseCorrectionDoesNotClearPreviouslyCapturedEvidence() {
        val guard = FaceAttemptGuard(timeline(adaptive = true))
        assertNull(guard.update(FaceTimeline.Phase.Colour(0), frame(0), 0))
        for (at in 1000L..3000L step 100) {
            assertNull(guard.update(FaceTimeline.Phase.Head(0, TurnDir.Left), frame(at).copy(pitch = 25f), at))
        }
        complete(guard, 0, TurnDir.Left, 3100)
        assertEquals(FaceAttemptIssue.FaceLost,
            guard.update(FaceTimeline.Phase.Head(0, TurnDir.Left), frame(3500, 30f, id = 8), 3500))
    }
}
