package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.IdAutoCaptureScheduler
import vn.vericlue.app.capture.IdQuality

class IdAutoCaptureSchedulerTest {
    private val frame = IdQuality(500.0, 0.0,
        "001095012345||Nguyễn Văn A|01011995|Nam|Hà Nội|15072021", portraitPresent = true)
    private fun q(timestamp: Long) = frame.copy(frameTimeNs = timestamp)

    @Test fun localRetriesContinueAfterTwentySecondsAndManyFailuresWithoutAShutter() {
        val scheduler = IdAutoCaptureScheduler()
        repeat(10) { index ->
            val time = index * 5000L
            val stamp = index * 10L + 1
            assertNull(scheduler.offer(q(stamp), time))
            val attempt = scheduler.offer(q(stamp + 1), time + 250)
            assertNotNull(attempt)
            scheduler.retry(attempt!!, time + 500)
        }
    }

    @Test fun cooldownAndInFlightFramesCannotAccumulateTowardTheNextAttempt() {
        val scheduler = IdAutoCaptureScheduler()
        assertNull(scheduler.offer(q(1), 0))
        val first = scheduler.offer(q(2), 250)!!
        assertNull(scheduler.offer(q(3), 500))
        scheduler.retry(first, 500)
        assertNull(scheduler.offer(q(4), 1000))
        assertNull(scheduler.offer(q(4), 1500))
        assertNull(scheduler.offer(q(5), 1600))
        assertNotNull(scheduler.offer(q(6), 1850))
    }

    @Test fun lateCompletionCannotClearOrRearmANewerAttempt() {
        val scheduler = IdAutoCaptureScheduler()
        scheduler.offer(q(1), 0)
        val first = scheduler.offer(q(2), 250)!!
        scheduler.cancel()
        assertFalse(scheduler.isCurrent(first))
        scheduler.offer(q(3), 500)
        val second = scheduler.offer(q(4), 750)!!
        scheduler.retry(first, 800)
        assertTrue(scheduler.isCurrent(second))
        scheduler.retry(second + 1, 900, serverRetry = true)
        assertTrue(scheduler.isCurrent(second))
        assertNull(scheduler.offer(q(5), 5000))
    }

    @Test fun serverRetriesWaitLongerButDoNotPermanentlyBlockTheSameCard() {
        val scheduler = IdAutoCaptureScheduler()
        scheduler.offer(q(1), 0)
        val first = scheduler.offer(q(2), 250)!!
        scheduler.retry(first, 500, serverRetry = true)
        assertNull(scheduler.offer(q(3), 5000))
        assertNull(scheduler.offer(q(4), 5500))
        val second = scheduler.offer(q(5), 5750)!!
        scheduler.retry(second, 6000, serverRetry = true)
        assertNull(scheduler.offer(q(6), 15000))
        assertNull(scheduler.offer(q(7), 16000))
        assertNotNull(scheduler.offer(q(8), 16250))
    }

    @Test fun zeroOrRepeatedFrameTimestampCannotTriggerAutomaticCapture() {
        val scheduler = IdAutoCaptureScheduler()
        repeat(5) { assertNull(scheduler.offer(q(0), it * 250L)) }
        scheduler.offer(q(1), 2000)
        repeat(5) { assertNull(scheduler.offer(q(1), 2250 + it * 250L)) }
    }
}
