package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.TurnDir

class HeadGuidanceTest {
    @Test fun offlineVoiceInAnotherEngineWinsOverDefaultNetworkVoice() {
        val search = HeadVoiceSearch()
        assertFalse(search.accept("default", hasOffline = false, hasNetwork = true))
        assertTrue(search.accept("offline", hasOffline = true, hasNetwork = false))
    }

    @Test fun networkVoiceIsRetriedOnlyOnceAfterOfflineSearchIsExhausted() {
        val search = HeadVoiceSearch()
        assertFalse(search.accept("network", hasOffline = false, hasNetwork = true))
        assertFalse(search.accept("missing", hasOffline = false, hasNetwork = false))
        assertEquals("network", search.fallback())
        assertTrue(search.accept("network", hasOffline = false, hasNetwork = true))
        assertNull(search.fallback())
    }

    private fun face(yaw: Float = 0f, at: Long, roll: Float = 0f) =
        FaceSignal(1, .45f, .5f, .45f, yaw, 120f, at * 1_000_000, roll = roll)

    @Test fun throttledWarningStillCancelsTheObsoleteHoldSpeech() {
        val policy = HeadCuePolicy()
        var playing: HeadCue? = null
        fun dispatch(cue: HeadCue, at: Long) = policy.dispatch(0, cue, at,
            stop = { playing = null }, say = { playing = it })
        dispatch(HeadCue.EaseBack, 1000)
        dispatch(HeadCue.Hold, 1100)
        assertEquals(HeadCue.Hold, playing)
        dispatch(HeadCue.EaseBack, 1200)
        assertNull(playing)
        dispatch(HeadCue.Hold, 1300)
        assertEquals(HeadCue.Hold, playing)
        dispatch(HeadCue.EaseBack, 3700)
        assertEquals(HeadCue.EaseBack, playing)
    }

    @Test fun holdAndOvershootReplaceTurnInstructionWithoutRepeatingEveryFrame() {
        val policy = HeadCuePolicy()
        assertEquals(HeadCue.Left, policy.poll(0, HeadCue.Left, 1000))
        assertEquals(HeadCue.Hold, policy.poll(0, HeadCue.Hold, 1100))
        assertNull(policy.poll(0, HeadCue.Hold, 1200))
        assertEquals(HeadCue.EaseBack, policy.poll(0, HeadCue.EaseBack, 1300))
        assertEquals(HeadCue.Hold, policy.poll(0, HeadCue.Hold, 1400))
        assertNull(policy.poll(0, HeadCue.EaseBack, 1500))
        assertNull(policy.poll(0, HeadCue.EaseBack, 2000))
        assertEquals(HeadCue.EaseBack, policy.poll(0, HeadCue.EaseBack, 3900))
        assertEquals(HeadCue.Center, policy.poll(1, HeadCue.Center, 4000))
    }

    @Test fun speechAndFallbackClearlyDistinguishTurnHoldAndReturn() {
        assertEquals("Dừng, giữ yên", HeadCue.Hold.text)
        assertEquals("Nhìn thẳng", HeadCue.Center.text)
        assertEquals(3, setOf(HeadCue.Left.beeps, HeadCue.Hold.beeps, HeadCue.Center.beeps).size)
        assertEquals(HeadCue.Straighten, headCue(TurnDir.Left, face(26f, 1000, 18f), false))
        assertEquals(HeadCue.EaseBack, headCue(TurnDir.Right, face(-48f, 1000), false))
        assertEquals(HeadCue.Hold, headCue(TurnDir.Left, face(26f, 1000), false))
        assertEquals(HeadCue.Center, headCue(TurnDir.Left, face(26f, 1000), true))
        assertEquals(HeadCue.FindFace, headCue(TurnDir.Left, null, false))
    }

    @Test fun practiceNeedsBothDirectionsAndReturnToCenterAndCanRestart() {
        val practice = HeadTurnPractice()
        fun feed(yaw: Float, first: Long, last: Long) {
            for (at in first..last step 100L) practice.update(face(yaw, at), at)
        }
        feed(0f, 1000, 1600)
        assertEquals(TurnDir.Left, practice.direction)
        feed(-26f, 1700, 3000)
        assertEquals(1, practice.step)
        feed(26f, 3100, 4100)
        assertEquals(2, practice.step)
        feed(0f, 4200, 4800)
        assertEquals(TurnDir.Right, practice.direction)
        feed(-26f, 4900, 5900)
        assertEquals(4, practice.step)
        feed(0f, 6000, 6600)
        assertTrue(practice.ready)
        practice.reset()
        assertFalse(practice.ready)
        assertEquals(0, practice.step)
    }

    @Test fun practiceDoesNotCountTiltOvershootOrStaleFramesAsHolding() {
        val practice = HeadTurnPractice()
        for (at in 1000L..1600L step 100) practice.update(face(at = at), at)
        for (at in 1700L..2600L step 100) practice.update(face(26f, at, 18f), at)
        assertEquals(1, practice.step)
        for (at in 2700L..3600L step 100) practice.update(face(55f, at), at)
        assertEquals(1, practice.step)
        for (at in 3700L..4600L step 100) practice.update(face(26f, at), at + 1000)
        assertEquals(1, practice.step)
    }
}
