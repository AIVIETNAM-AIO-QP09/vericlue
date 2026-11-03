package vn.vericlue.app.capture

/** Serial automatic attempts with fresh observations and bounded retry spacing, not a retry limit. */
class IdAutoCaptureScheduler {
    private val detector = IdAutoCapture()
    private var generation = 0L
    private var active: Long? = null
    private var lastFrameNs = 0L
    private var nextAttemptMs = 0L
    private var localFailures = 0
    private var serverFailures = 0

    /** Returns a token only after new qualifying frames arrive outside an active/cooling attempt. */
    fun offer(quality: IdQuality, nowMs: Long): Long? {
        if (quality.frameTimeNs <= lastFrameNs) return null
        lastFrameNs = quality.frameTimeNs
        if (active != null || nowMs < nextAttemptMs) {
            detector.reset()
            return null
        }
        if (!detector.offer(quality)) return null
        detector.reset()
        return (++generation).also { active = it }
    }

    /** Local failures wait 1/2/4 seconds; server retries wait 5/10/20 seconds to preserve scan quota. */
    fun retry(attempt: Long, nowMs: Long, serverRetry: Boolean = false) {
        if (!isCurrent(attempt)) return
        active = null
        detector.reset()
        val delayMs = if (serverRetry) {
            serverFailures = (serverFailures + 1).coerceAtMost(3)
            localFailures = 0
            5000L * (1L shl (serverFailures - 1))
        } else {
            localFailures = (localFailures + 1).coerceAtMost(3)
            1000L * (1L shl (localFailures - 1))
        }
        nextAttemptMs = nowMs + delayMs
    }

    fun isCurrent(attempt: Long): Boolean = active == attempt

    /** Invalidate callbacks immediately when leaving, including before a navigation animation ends. */
    fun cancel() {
        generation++
        active = null
        detector.reset()
        nextAttemptMs = 0
        localFailures = 0
        serverFailures = 0
    }
}
