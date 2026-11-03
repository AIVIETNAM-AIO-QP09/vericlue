package vn.vericlue.app.capture

import java.util.concurrent.Executor

/**
 * Stamps CameraX event dispatch before the main queue delays delivery. The delegate must execute
 * callbacks serially on one thread; the timestamp accessor is confined to those callbacks.
 * Use one instance per recording. This removes queue delay, not encoder latency, from estimates.
 */
internal class RecordingEventClock(
    private val serialExecutor: Executor,
    private val nowNanos: () -> Long,
) : Executor {
    private var activeDispatchNs: Long? = null

    override fun execute(command: Runnable) {
        val dispatchedAtNs = nowNanos()
        serialExecutor.execute {
            val previous = activeDispatchNs
            activeDispatchNs = dispatchedAtNs
            try {
                command.run()
            } finally {
                activeDispatchNs = previous
            }
        }
    }

    fun dispatchTimeNanos(): Long = checkNotNull(activeDispatchNs) {
        "Recording dispatch time is only available inside its callback"
    }
}
