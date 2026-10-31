package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.Routes

class ManualDemoCameraTest {
    @Test fun completionClosesCameraWhileVoiceCaptureKeepsItAvailable() {
        assertTrue(FlowRules.closesCameraOnResult(Routes.ManualDemoComplete))
        assertTrue(FlowRules.closesCameraOnResult(Routes.Success))
        assertTrue(FlowRules.closesCameraOnResult(Routes.Review))
        assertFalse(FlowRules.closesCameraOnResult(Routes.Voice))
        assertFalse(FlowRules.closesCameraOnResult(Routes.Uploading))
    }
}
