package vn.vericlue.app

import java.util.concurrent.Executor
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.RecordingEventClock

class RecordingEventClockTest {
    private class QueuedExecutor : Executor {
        private val commands = ArrayDeque<Runnable>()
        override fun execute(command: Runnable) { commands.addLast(command) }
        fun runNext() { commands.removeFirst().run() }
    }

    @Test fun delayedMainQueueDoesNotShiftRecordingOriginEstimate() {
        var nowNs = 1_000_000_000L
        val main = QueuedExecutor()
        val clock = RecordingEventClock(main) { nowNs }
        val recordedDurationNs = 100_000_000L
        var estimatedOriginNs: Long? = null
        clock.execute {
            estimatedOriginNs = clock.dispatchTimeNanos() - recordedDurationNs
        }
        assertNull(estimatedOriginNs)
        nowNs = 1_600_000_000L
        main.runNext()
        assertEquals(900_000_000L, estimatedOriginNs)
    }

    @Test fun queuedEventsKeepTheirOwnDispatchTimesAndRunOnlyOnDelegate() {
        var nowNs = 10L
        val main = QueuedExecutor()
        val clock = RecordingEventClock(main) { nowNs }
        val seen = mutableListOf<Long>()
        clock.execute { seen += clock.dispatchTimeNanos() }
        nowNs = 20L
        clock.execute { seen += clock.dispatchTimeNanos() }
        assertTrue(seen.isEmpty())
        nowNs = 300L
        main.runNext()
        main.runNext()
        assertEquals(listOf(10L, 20L), seen)
    }

    @Test fun timestampIsUnavailableOutsideCallback() {
        val main = QueuedExecutor()
        val clock = RecordingEventClock(main) { 10L }
        assertThrows(IllegalStateException::class.java) { clock.dispatchTimeNanos() }
        clock.execute { assertEquals(10L, clock.dispatchTimeNanos()) }
        assertThrows(IllegalStateException::class.java) { clock.dispatchTimeNanos() }
        main.runNext()
        assertThrows(IllegalStateException::class.java) { clock.dispatchTimeNanos() }
    }

    @Test fun callbackFailurePropagatesAndClearsTimestamp() {
        val main = QueuedExecutor()
        val clock = RecordingEventClock(main) { 10L }
        val failure = IllegalArgumentException("callback failure")
        clock.execute {
            assertEquals(10L, clock.dispatchTimeNanos())
            throw failure
        }
        assertSame(failure, assertThrows(IllegalArgumentException::class.java) { main.runNext() })
        assertThrows(IllegalStateException::class.java) { clock.dispatchTimeNanos() }
    }

    @Test fun nestedCallbackRestoresOuterTimestampEvenAfterFailure() {
        var nowNs = 10L
        val clock = RecordingEventClock(Executor { it.run() }) { nowNs }
        clock.execute {
            assertEquals(10L, clock.dispatchTimeNanos())
            nowNs = 20L
            clock.execute { assertEquals(20L, clock.dispatchTimeNanos()) }
            assertEquals(10L, clock.dispatchTimeNanos())
            nowNs = 30L
            assertThrows(IllegalArgumentException::class.java) {
                clock.execute {
                    assertEquals(30L, clock.dispatchTimeNanos())
                    throw IllegalArgumentException("nested failure")
                }
            }
            assertEquals(10L, clock.dispatchTimeNanos())
        }
        assertThrows(IllegalStateException::class.java) { clock.dispatchTimeNanos() }
    }
}
