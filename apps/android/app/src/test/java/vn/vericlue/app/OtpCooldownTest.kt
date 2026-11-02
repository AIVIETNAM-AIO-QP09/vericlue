package vn.vericlue.app

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.ui.OtpCooldown

@OptIn(ExperimentalCoroutinesApi::class)
class OtpCooldownTest {
    @Test fun resendRestartsTheEntireCountdownAndRejectsRapidDuplicateTaps() = runTest {
        val timer = OtpCooldown()
        assertFalse(timer.restart())
        launch { timer.run() }
        advanceUntilIdle()
        assertEquals(0, timer.seconds)
        assertTrue(timer.restart())
        assertFalse(timer.restart())
        assertEquals(1, timer.generation)
        launch { timer.run() }
        runCurrent()
        advanceTimeBy(1000)
        runCurrent()
        assertEquals(44, timer.seconds)
        advanceUntilIdle()
        assertEquals(0, timer.seconds)
        assertTrue(timer.restart())
        assertEquals(2, timer.generation)
    }

    @Test fun leavingTheScreenCancelsTheTicker() = runTest {
        val timer = OtpCooldown()
        val job = launch { timer.run() }
        runCurrent()
        advanceTimeBy(2000)
        runCurrent()
        val remaining = timer.seconds
        job.cancel()
        advanceUntilIdle()
        assertEquals(43, remaining)
        assertEquals(remaining, timer.seconds)
    }
}
