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
import vn.vericlue.app.capture.QualityGate
import vn.vericlue.app.capture.TurnTracker
import vn.vericlue.app.capture.Wav
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorStep
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.Routes

class CaptureTest {
    private fun face(width: Float = 0.45f, x: Float = 0.5f, y: Float = 0.45f, luma: Float = 120f, faces: Int = 1) =
        FaceSignal(faces, width, x, y, 0f, luma, 0L)

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
