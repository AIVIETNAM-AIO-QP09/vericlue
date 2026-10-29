package vn.vericlue.app.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** QR results belong to one card side/retake, including asynchronous scanner callbacks. */
internal class QrCaptureState {
    private var generation = 0L
    private val value = MutableStateFlow<String?>(null)
    private var seenAtNs = 0L
    val qr: StateFlow<String?> = value

    @Synchronized fun generation(): Long = generation

    @Synchronized fun clear() {
        generation++
        value.value = null
        seenAtNs = 0L
    }

    @Synchronized fun update(frameGeneration: Long, raw: String?, timestampNs: Long = 0) {
        if (frameGeneration == generation && raw != null) {
            value.value = raw
            seenAtNs = timestampNs
        }
    }

    @Synchronized fun recentlySeen(frameGeneration: Long, timestampNs: Long): Boolean {
        return frameGeneration == generation && seenAtNs > 0 && timestampNs >= seenAtNs &&
            timestampNs - seenAtNs <= IdAutoCapture.QR_HOLD_NS
    }
}
