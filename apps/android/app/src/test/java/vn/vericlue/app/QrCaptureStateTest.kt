package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.vericlue.app.capture.QrCaptureState

class QrCaptureStateTest {
    @Test fun openingAnotherSideClearsThePreviousQr() {
        val state = QrCaptureState()
        state.update(state.generation(), "front")
        assertEquals("front", state.qr.value)
        state.clear()
        assertNull(state.qr.value)
        state.update(state.generation(), "back")
        assertEquals("back", state.qr.value)
    }

    @Test fun lateResultFromBeforeRetakeCannotRestoreTheOldQr() {
        val state = QrCaptureState()
        val oldFrame = state.generation()
        state.clear()
        state.update(oldFrame, "old-front")
        assertNull(state.qr.value)
        state.update(state.generation(), "retaken-front")
        state.update(oldFrame, "old-front")
        assertEquals("retaken-front", state.qr.value)
    }
}
