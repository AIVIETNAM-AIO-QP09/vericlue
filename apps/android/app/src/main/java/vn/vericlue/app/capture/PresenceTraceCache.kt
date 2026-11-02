package vn.vericlue.app.capture

import java.io.File

/** One private diagnostic, erased on drop/withdrawal, replaced at the next attempt. */
class PresenceTraceCache(private val file: File, private val nowMs: () -> Long = { System.currentTimeMillis() }) {
    fun save(trace: PresenceDebugTrace) {
        if (!trace.enabled) return
        file.writeText(trace.toJson())
        file.setLastModified(nowMs())
    }

    fun clear() { file.delete() }

    fun mediaDeleted(preserveDiagnostics: Boolean) {
        if (!preserveDiagnostics) clear()
    }

    fun prune() {
        if (file.exists() && nowMs() - file.lastModified() >= TTL_MS) clear()
    }

    companion object { const val TTL_MS = 15 * 60_000L }
}
