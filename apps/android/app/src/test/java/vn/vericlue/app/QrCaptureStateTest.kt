package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
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

    @Test fun recentFeedbackExpiresAndCannotCrossARetake() {
        val state = QrCaptureState()
        val generation = state.generation()
        state.update(generation, "read-on-this-side", 100)
        state.update(generation, null, 200)
        assertTrue(state.recentlySeen(generation, 200))
        assertFalse(state.recentlySeen(generation, 99))
        assertFalse(state.recentlySeen(generation, 1_500_000_101))
        state.clear()
        assertFalse(state.recentlySeen(state.generation(), 200))
        state.update(generation, "late-old-frame", 250)
        assertFalse(state.recentlySeen(state.generation(), 250))
    }
}
