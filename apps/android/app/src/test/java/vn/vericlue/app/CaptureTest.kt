package vn.vericlue.app

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.ColorSlot
import vn.vericlue.app.capture.FaceSignal
import vn.vericlue.app.capture.HeadTurnGuide
import vn.vericlue.app.capture.QualityGate
import vn.vericlue.app.capture.SegmentHoldTracker
import vn.vericlue.app.capture.TurnPoseState
import vn.vericlue.app.capture.TurnTracker
import vn.vericlue.app.capture.Wav
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorStep
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.Routes
import vn.vericlue.app.flow.TurnDir

class CaptureTest {
    private fun face(width: Float = 0.45f, x: Float = 0.5f, y: Float = 0.45f, luma: Float = 120f, faces: Int = 1, yaw: Float = 0f) =
        FaceSignal(faces, width, x, y, yaw, luma, 0L)

    @Test fun guideDiscardsOldFutureAndPreviousSegmentFrames() {
        val current = face(yaw = 26f).copy(timestampNs = 2_000_000_000L)
        assertEquals(current, HeadTurnGuide.freshFace(current, 2100, 1000))
        assertNull(HeadTurnGuide.freshFace(current, 2400, 1000))
        assertNull(HeadTurnGuide.freshFace(current, 1900, 1000))
        assertNull(HeadTurnGuide.freshFace(current, 2100, 2050))
    }

    @Test
    fun delayedAnalyzerFramesCannotCompleteAHold() {
        val tracker = SegmentHoldTracker(segmentStartMs = 1000L)
        val old = face(yaw = 26f).copy(timestampNs = 1100_000_000L)
        for (offset in 0L..900L step 100L) {
            assertFalse(tracker.update(TurnDir.Left, old.copy(timestampNs = (1100L + offset) * 1_000_000L), 4000L + offset))
        }
        assertFalse(tracker.completed)
    }

    @Test
    fun analyzerGapsOrReversedTimeCannotCompleteAHold() {
        val good = face(yaw = 26f)
        for (badTime in listOf(1000L, -100L, 0L)) {
            val tracker = SegmentHoldTracker()
            assertFalse(tracker.update(TurnDir.Left, good, 0))
            assertFalse(tracker.update(TurnDir.Left, good, badTime))
            assertFalse(tracker.completed)
        }
        val tracker = SegmentHoldTracker()
        assertFalse(tracker.update(TurnDir.Left, good, 0))
        assertFalse(tracker.update(TurnDir.Left, good, 200))
        assertFalse(tracker.update(TurnDir.Left, good.copy(roll = 18f), 300))
        for (time in 400L..1200L step 100L) assertFalse(tracker.update(TurnDir.Left, good, time))
        assertTrue(tracker.update(TurnDir.Left, good, 1300))
    }

    @Test
    fun tiltedHeadCannotShowGreenOrCompleteTheHold() {
        for (pose in listOf(face(yaw = 26f).copy(pitch = 16f), face(yaw = 26f).copy(roll = -16f))) {
            assertEquals(TurnPoseState.Warn, HeadTurnGuide.evaluatePose(TurnDir.Left, pose))
            assertEquals(TurnPoseState.Warn, HeadTurnGuide.evaluatePose(null, pose.copy(yaw = 0f)))
            assertEquals(TurnPoseState.Warn, HeadTurnGuide.evaluatePose(TurnDir.Left, pose, segmentCompleted = true))
            assertEquals("Giữ đầu thẳng, tránh nghiêng hoặc cúi/ngẩng", HeadTurnGuide.guidanceText(TurnDir.Left, pose))
            val tracker = SegmentHoldTracker()
            assertFalse(tracker.update(TurnDir.Left, pose, 0))
            assertFalse(tracker.update(TurnDir.Left, pose, 1000))
            assertFalse(tracker.completed)
        }
        assertEquals(TurnPoseState.Hold, HeadTurnGuide.evaluatePose(TurnDir.Left, face(yaw = 26f).copy(pitch = 5f, roll = 5f)))
    }

    @Test
    fun invalidAngleNeverShowsGreenOrCompletesHold() {
        val invalid = face(yaw = Float.NaN)
        assertEquals(TurnPoseState.Warn, HeadTurnGuide.evaluatePose(TurnDir.Left, invalid))
        val tracker = SegmentHoldTracker()
        assertFalse(tracker.update(TurnDir.Left, invalid, 0))
        assertFalse(tracker.update(TurnDir.Left, invalid, 1000))
        assertFalse(tracker.completed)
    }

    @Test
    fun headTurnGuideHelpsHoldOrCorrectWithoutDecidingPass() {
        // Missing FaceSignal: always neutral instruction, never confirms holding a pose.
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Left, null, remainingSeconds = 4),
        )
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Right, null, remainingSeconds = 4),
        )
        assertEquals(
            "Giữ yên, nhìn thẳng vào camera",
            HeadTurnGuide.guidanceText(null, null, remainingSeconds = 4),
        )
        // Missing or multiple faces.
        assertEquals(
            "Đưa khuôn mặt vào khung",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(faces = 0), remainingSeconds = 3),
        )
        assertEquals(
            "Chỉ để một khuôn mặt trong khung",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(faces = 2), remainingSeconds = 3),
        )
        // Not turned far enough yet.
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(yaw = 5f), remainingSeconds = 4),
        )
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = -5f), remainingSeconds = 4),
        )
        // Correct direction in target range (ML Kit on unmirrored front frame: Left > 0, Right < 0).
        assertEquals(
            "Giữ hướng này đến khi đổi hướng dẫn",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(yaw = 26f), remainingSeconds = 3),
        )
        assertEquals(
            "Giữ hướng này đến khi đổi hướng dẫn",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = -26f), remainingSeconds = 3),
        )
        // Opposite direction must never confirm holding the pose.
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(yaw = -26f), remainingSeconds = 3),
        )
        assertEquals(
            "Quay chậm theo hướng mũi tên",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = 26f), remainingSeconds = 3),
        )
        // Turned too far or drifted near the frame edge in the target direction.
        assertEquals(
            "Quay vừa phải, giữ mặt trong khung",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(yaw = 46f), remainingSeconds = 2),
        )
        assertEquals(
            "Quay vừa phải, giữ mặt trong khung",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = -46f), remainingSeconds = 2),
        )
        assertEquals(
            "Quay vừa phải, giữ mặt trong khung",
            HeadTurnGuide.guidanceText(TurnDir.Left, face(x = 0.78f, yaw = 28f), remainingSeconds = 2),
        )
        // Center segment.
        assertEquals(
            "Đưa khuôn mặt vào giữa khung hình",
            HeadTurnGuide.guidanceText(null, face(x = 0.78f, yaw = 4f), remainingSeconds = 2),
        )
        assertEquals(
            "Quay về giữa, nhìn thẳng vào camera",
            HeadTurnGuide.guidanceText(null, face(yaw = -24f), remainingSeconds = 4),
        )
        assertEquals(
            "Giữ yên, nhìn thẳng vào camera",
            HeadTurnGuide.guidanceText(null, face(yaw = 3f), remainingSeconds = 2),
        )
        // Once the segment hold completes, cue the user to return to center and wait for the next step.
        assertEquals(
            "Tạm giữ đủ góc, nhìn thẳng",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = -26f), remainingSeconds = 2, segmentCompleted = true),
        )
        assertEquals(
            "Giữ yên, nhìn thẳng chờ bước tiếp",
            HeadTurnGuide.guidanceText(TurnDir.Right, face(yaw = -3f), remainingSeconds = 2, segmentCompleted = true),
        )
    }

    @Test
    fun staleFrameCannotCompleteNewSegmentHold() {
        val tracker = SegmentHoldTracker(requiredHoldMs = 850L, segmentStartMs = 4_000L)
        val stale = FaceSignal(
            faces = 1,
            widthFraction = 0.4f,
            centerX = 0.5f,
            centerY = 0.45f,
            yaw = 26f,
            pitch = 0f,
            roll = 0f,
            luma = 120f,
            timestampNs = 3_900_000_000L,
        )
        assertFalse(tracker.update(TurnDir.Left, stale, nowMs = 3_900L))
        assertFalse(tracker.update(TurnDir.Left, stale, nowMs = 4_900L))
        assertFalse(tracker.completed)
    }

    @Test
    fun segmentHoldTrackerCompletesAfterSustainedTargetAngle() {
        val tracker = SegmentHoldTracker(requiredHoldMs = 850L)
        assertEquals(TurnPoseState.TurnMore, HeadTurnGuide.evaluatePose(TurnDir.Right, null))
        assertEquals(TurnPoseState.TurnMore, HeadTurnGuide.evaluatePose(TurnDir.Right, face(yaw = -10f)))
        assertEquals(TurnPoseState.Hold, HeadTurnGuide.evaluatePose(TurnDir.Right, face(yaw = -26f)))
        assertEquals(TurnPoseState.Warn, HeadTurnGuide.evaluatePose(TurnDir.Right, face(yaw = -42f)))

        assertFalse(tracker.update(TurnDir.Right, face(yaw = -12f), 0L))
        assertFalse(tracker.update(TurnDir.Right, face(yaw = -26f), 100L))
        assertFalse(tracker.update(TurnDir.Right, face(yaw = -28f), 300L))
        assertFalse(tracker.update(TurnDir.Right, face(yaw = -28f), 500L))
        assertFalse(tracker.update(TurnDir.Right, face(yaw = -28f), 700L))
        assertTrue(tracker.update(TurnDir.Right, face(yaw = -27f), 950L))
        assertTrue(tracker.completed)
        assertFalse(tracker.update(TurnDir.Right, face(yaw = -27f), 1100L))
        assertEquals(
            TurnPoseState.Completed,
            HeadTurnGuide.evaluatePose(TurnDir.Right, face(yaw = -2f), segmentCompleted = tracker.completed),
        )
    }

    @Test
    fun qualityGateGivesOneHintAtATime() {
        assertEquals(FramingState.NoFace, QualityGate.evaluate(null))
        assertEquals(FramingState.NoFace, QualityGate.evaluate(face(faces = 0)))
        assertEquals(FramingState.LowLight, QualityGate.evaluate(face(luma = 30f, width = 0.1f)))
        assertEquals(FramingState.TooFar, QualityGate.evaluate(face(width = 0.2f)))
        assertEquals(FramingState.OffCenter, QualityGate.evaluate(face(x = 0.8f)))
        assertEquals(FramingState.Good, QualityGate.evaluate(face()))
    }

    @Test
    fun turnNeedsHoldThenBackToStraight() {
        val t = TurnTracker(thresholdDeg = 25f, holdMs = 300, straightDeg = 10f)
        assertFalse(t.update(30f, 0))
        assertFalse(t.update(30f, 200))
        assertFalse(t.update(30f, 350))
        assertTrue(t.turned)
        assertFalse(t.update(20f, 400))
        assertTrue(t.update(5f, 500))
    }

    @Test
    fun shortTurnDoesNotCount() {
        val t = TurnTracker(holdMs = 300)
        t.update(30f, 0)
        t.update(0f, 100)
        t.update(30f, 200)
        assertFalse(t.turned)
    }

    @Test
    fun colourScheduleFollowsTheServerChallenge() {
        val challenge = Challenge(
            challengeId = "c1",
            baselineMs = 1000,
            colorSequence = List(8) { ColorStep(if (it % 2 == 0) "#ffcc73" else "#73d9ff", 450, 150) },
        )
        val slots = ColorSchedule.from(challenge)
        assertEquals(10, slots.size)
        assertEquals(ColorSlot(null, ColorSchedule.BASELINE_RGB, 1000), slots.first())
        assertEquals(ColorSlot(0, "#ffcc73", 600), slots[1])
        assertNull(slots.last().index)
        assertTrue(ColorSchedule.isSafe(slots))
        assertTrue(ColorSchedule.isSafe(ColorSchedule.demo()))
    }

    @Test
    fun tooFastFlickerIsRejected() {
        assertFalse(ColorSchedule.isSafe(listOf(ColorSlot(0, "#ffffff", 200))))
    }

    @Test
    fun wavHeaderIs16kMono16Bit() {
        val pcm = ByteArray(32000)
        val wav = Wav.encode(pcm)
        assertEquals(44 + pcm.size, wav.size)
        val h = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals("RIFF", String(wav, 0, 4))
        assertEquals("WAVE", String(wav, 8, 4))
        assertEquals(1, h.getShort(22).toInt()) // mono
        assertEquals(16000, h.getInt(24))
        assertEquals(16, h.getShort(34).toInt()) // bits per sample
        assertEquals(pcm.size, h.getInt(40))
    }

    @Test
    fun onlyPassIsSuccessAndUnknownIsNotAScreen() {
        assertEquals(Routes.Success, FlowRules.routeForStatus("pass", null, false))
        assertEquals(Routes.Review, FlowRules.routeForStatus("review", null, false))
        assertEquals(Routes.RetryQuality, FlowRules.routeForStatus("retry", "MORE_LIGHT", false))
        assertEquals(Routes.RetryChallenge, FlowRules.routeForStatus("retry", null, false))
        assertEquals(Routes.Voice, FlowRules.routeForStatus("voice_challenge", null, false))
        assertEquals(Routes.VoiceAgain, FlowRules.routeForStatus("voice_challenge", null, true))
        assertNull(FlowRules.routeForStatus("error", null, false))
        assertNull(FlowRules.routeForStatus("degraded", null, false))
    }
}
