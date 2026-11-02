package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.TurnDir

class SegmentReturnTrackerTest {
    private fun face(yaw: Float = 0f, at: Long) =
        FaceSignal(1, .45f, .5f, .45f, yaw, 120f, at * 1_000_000)

    @Test fun oneExcursionAndReturnDoesNotAskForTheSameTurnAgainInEitherOrder() {
        for (order in listOf(listOf(TurnDir.Left, TurnDir.Right), listOf(TurnDir.Right, TurnDir.Left))) {
            for ((index, dir) in order.withIndex()) {
                val start = 1000L + index * 5000L
                val tracker = SegmentReturnTracker(segmentStartMs = start)
                val hold = SegmentHoldTracker(segmentStartMs = start)
                val side = face(if (dir == TurnDir.Left) 26f else -26f, start + 100)
                tracker.update(dir, side, start + 100)
                hold.update(dir, side, start + 100)
                val center = face(at = start + 300)
                tracker.update(dir, center, start + 300)
                hold.update(dir, center, start + 300)
                assertTrue(tracker.waitingForNext)
                assertFalse(hold.completed)
                assertEquals(HeadCue.Center, headCue(dir, center, hold.completed, tracker.waitingForNext))
                assertEquals(HeadCue.Center, headCue(dir, side.copy(timestampNs = (start + 500) * 1_000_000), false, tracker.waitingForNext))
                assertEquals("Giữ yên, nhìn thẳng chờ hướng tiếp",
                    HeadTurnGuide.guidanceText(dir, center, waitingForNext = tracker.waitingForNext))
            }
        }
    }

    @Test fun holdingTheSideDoesNotLatchBeforeReturningToCenter() {
        val tracker = SegmentReturnTracker(segmentStartMs = 1000)
        for (at in 1100L..2300L step 100) tracker.update(TurnDir.Left, face(26f, at), at)
        assertFalse(tracker.waitingForNext)
        tracker.update(TurnDir.Left, face(at = 2400), 2400)
        assertTrue(tracker.waitingForNext)
    }

    @Test fun wrongSideAndInitialCenterCannotLatchWaiting() {
        for (dir in listOf(TurnDir.Left, TurnDir.Right)) {
            val tracker = SegmentReturnTracker(segmentStartMs = 1000)
            tracker.update(dir, face(at = 1100), 1100)
            tracker.update(dir, face(if (dir == TurnDir.Left) -26f else 26f, 1200), 1200)
            tracker.update(dir, face(at = 1300), 1300)
            assertFalse(tracker.waitingForNext)
        }
    }

    @Test fun unusableFramesCannotEstablishAnExcursion() {
        val side = face(26f, 1100)
        val invalid = listOf(null, side.copy(faces = 0), side.copy(faces = 2),
            side.copy(yaw = Float.NaN), side.copy(pitch = Float.POSITIVE_INFINITY),
            side.copy(centerX = Float.NaN), side.copy(centerY = Float.POSITIVE_INFINITY),
            side.copy(roll = 18f), side.copy(yaw = 45f), side.copy(centerX = .9f),
            side.copy(timestampNs = 0), side.copy(timestampNs = 900_000_000),
            side.copy(timestampNs = 1_200_000_000))
        for (bad in invalid) {
            val tracker = SegmentReturnTracker(segmentStartMs = 1000)
            tracker.update(TurnDir.Left, bad, 1100)
            tracker.update(TurnDir.Left, face(at = 1300), 1300)
            assertFalse(tracker.waitingForNext)
        }
        val stale = SegmentReturnTracker(segmentStartMs = 1000)
        stale.update(TurnDir.Left, side, 1500)
        stale.update(TurnDir.Left, face(at = 1600), 1600)
        assertFalse(stale.waitingForNext)
    }

    @Test fun missingStaleOrRepeatedCenterCannotCompleteAnObservedExcursion() {
        for ((bad, at) in listOf(null to 1500L, face(at = 1100) to 1500L,
                face(at = 900) to 1500L, face(at = 1200).copy(faces = 0) to 1500L,
                face(at = 1100) to 1100L)) {
            val tracker = SegmentReturnTracker(segmentStartMs = 1000)
            tracker.update(TurnDir.Left, face(26f, 1100), 1100)
            tracker.update(TurnDir.Left, bad, at)
            assertFalse(tracker.waitingForNext)
        }
    }

    @Test fun freshNeutralReturnAfterAnObservationGapDoesNotRequireAContinuousHold() {
        for (missing in listOf(false, true)) {
            val tracker = SegmentReturnTracker(segmentStartMs = 1000)
            val hold = SegmentHoldTracker(segmentStartMs = 1000)
            val side = face(26f, 1100)
            tracker.update(TurnDir.Left, side, 1100)
            hold.update(TurnDir.Left, side, 1100)
            if (missing) tracker.update(TurnDir.Left, null, 1500)
            assertFalse(tracker.waitingForNext)
            val center = face(at = 2000)
            tracker.update(TurnDir.Left, center, 2000)
            hold.update(TurnDir.Left, center, 2000)
            assertTrue(tracker.waitingForNext)
            assertFalse(hold.completed)
            assertEquals(HeadCue.Center, headCue(TurnDir.Left, center, false, tracker.waitingForNext))
        }
    }

    @Test fun wrongSideCannotCompleteButDoesNotEraseAnEarlierValidExcursion() {
        val tracker = SegmentReturnTracker(segmentStartMs = 1000)
        tracker.update(TurnDir.Left, face(26f, 1100), 1100)
        tracker.update(TurnDir.Left, face(-26f, 1200), 1200)
        assertFalse(tracker.waitingForNext)
        tracker.update(TurnDir.Left, face(at = 1300), 1300)
        assertTrue(tracker.waitingForNext)
    }

    @Test fun waitingStillPrioritizesImmediatePoseCorrections() {
        val tracker = SegmentReturnTracker(segmentStartMs = 1000)
        tracker.update(TurnDir.Left, face(26f, 1100), 1100)
        tracker.update(TurnDir.Left, face(at = 1300), 1300)
        assertTrue(tracker.waitingForNext)
        assertEquals(HeadCue.FindFace, headCue(TurnDir.Left, null, false, tracker.waitingForNext))
        assertEquals(HeadCue.Straighten, headCue(TurnDir.Left, face(at = 1400).copy(roll = 18f), false, tracker.waitingForNext))
        assertEquals(HeadCue.EaseBack, headCue(TurnDir.Left, face(45f, 1400), false, tracker.waitingForNext))
        assertEquals(HeadCue.FindFace, headCue(TurnDir.Left, face(at = 1400).copy(centerX = .9f), false, tracker.waitingForNext))
        tracker.update(TurnDir.Left, null, 1500)
        assertTrue(tracker.waitingForNext)
        assertEquals(HeadCue.Center, headCue(TurnDir.Left, face(at = 1600), false, tracker.waitingForNext))
    }

    @Test fun aNewSegmentRequiresItsOwnExcursionAndKeepsLocalCompletionSeparate() {
        val first = SegmentReturnTracker(segmentStartMs = 1000)
        first.update(TurnDir.Left, face(26f, 1100), 1100)
        first.update(TurnDir.Left, face(at = 1300), 1300)
        val next = SegmentReturnTracker(segmentStartMs = 6000)
        next.update(TurnDir.Right, face(at = 6100), 6100)
        assertFalse(next.waitingForNext)
        assertEquals(HeadCue.Right, headCue(TurnDir.Right, face(at = 6100), false, next.waitingForNext))
        assertEquals(HeadCue.Center, headCue(TurnDir.Right, face(-26f, 6200), true, next.waitingForNext))
        assertEquals("Tạm giữ đủ góc, nhìn thẳng",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(-26f, 6200), segmentCompleted = true, waitingForNext = true))
    }
}
