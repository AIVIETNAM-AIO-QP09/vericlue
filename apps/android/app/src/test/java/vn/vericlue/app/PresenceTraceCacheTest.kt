package vn.vericlue.app

import java.io.File
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import vn.vericlue.app.capture.PresenceDebugTrace
import vn.vericlue.app.capture.PresenceTraceCache

class PresenceTraceCacheTest {
    @get:Rule val temp = TemporaryFolder()

    @Test fun stoppedOrWithdrawnDiagnosticsCanBeErasedAndExpiredDataIsPruned() {
        var now = System.currentTimeMillis()
        val file = File(temp.root, "trace.json")
        val cache = PresenceTraceCache(file) { now }
        cache.save(PresenceDebugTrace(enabled = true))
        assertTrue(file.exists())
        now += PresenceTraceCache.TTL_MS + 1
        cache.prune()
        assertFalse(file.exists())
        cache.save(PresenceDebugTrace(enabled = true))
        cache.clear()
        assertFalse(file.exists())
        cache.save(PresenceDebugTrace())
        assertFalse(file.exists())
    }

    @Test fun mediaAcknowledgmentPreservesTheDiagnosticUntilDropOrExpiry() {
        val file = File(temp.root, "trace.json")
        val cache = PresenceTraceCache(file)
        cache.save(PresenceDebugTrace(enabled = true))
        cache.mediaDeleted(preserveDiagnostics = true)
        assertTrue(file.exists())
        cache.mediaDeleted(preserveDiagnostics = false)
        assertFalse(file.exists())
    }
}
