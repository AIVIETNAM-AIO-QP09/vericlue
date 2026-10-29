package vn.vericlue.app.capture

import java.io.File
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.withTimeoutOrNull

/** Timeout keeps the recording available for the next wait; it never means no video. */
sealed interface VideoResult {
    data class Ready(val file: File) : VideoResult
    data object NotRecorded : VideoResult
    data object Timeout : VideoResult
}

/** Waits for CameraX's completion result, not the server's finalize endpoint. */
internal suspend fun awaitVideoFile(
    file: File?,
    finalized: Deferred<Boolean>?,
    timeoutMs: Long = 3000,
): VideoResult {
    if (file == null || finalized == null) return VideoResult.NotRecorded
    val success = withTimeoutOrNull(timeoutMs) { finalized.await() } ?: return VideoResult.Timeout
    return if (success && file.isFile && file.length() > 0) VideoResult.Ready(file) else VideoResult.NotRecorded
}
