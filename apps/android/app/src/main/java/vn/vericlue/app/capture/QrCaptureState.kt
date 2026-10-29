package vn.vericlue.app.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** QR results belong to one card side/retake, including asynchronous scanner callbacks. */
internal class QrCaptureState {
    private var generation = 0L
    private val value = MutableStateFlow<String?>(null)
    val qr: StateFlow<String?> = value

    @Synchronized fun generation(): Long = generation

    @Synchronized fun clear() {
        generation++
        value.value = null
    }

    @Synchronized fun update(frameGeneration: Long, raw: String?) {
        if (frameGeneration == generation && raw != null) value.value = raw
    }
}
