package vn.vericlue.app.capture

/** One scanner result belongs to one mounted route and one upload, including late SDK callbacks. */
class DocumentCaptureAttempt {
    enum class Phase { Ready, Opening, Scanning, Reading, Finished, Closed }
    var phase = Phase.Ready
        private set
    private var generation = 0L

    fun begin(): Long? {
        if (phase != Phase.Ready) return null
        phase = Phase.Opening
        return ++generation
    }

    fun opened(ticket: Long): Boolean {
        if (!current(ticket) || phase != Phase.Opening) return false
        phase = Phase.Scanning
        return true
    }

    fun result(): Long? {
        if (phase != Phase.Scanning) return null
        phase = Phase.Reading
        return generation
    }

    fun current(ticket: Long): Boolean = ticket == generation && phase !in setOf(Phase.Closed, Phase.Finished)

    fun retry(ticket: Long) {
        if (current(ticket)) phase = Phase.Ready
    }

    fun finish(ticket: Long) {
        if (current(ticket)) phase = Phase.Finished
    }

    fun close() { generation++; phase = Phase.Closed }
}
