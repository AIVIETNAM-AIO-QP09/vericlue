package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Test
import vn.vericlue.app.capture.VoiceCaptureFailure
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.Routes

class VoiceCaptureFailureRouteTest {
    @Test fun audioFailureWithMicPermissionOffersAnotherRecording() {
        for (cameraGranted in listOf(false, true)) {
            assertEquals(Routes.NoVoice, FlowRules.voiceCaptureFailureRoute(
                VoiceCaptureFailure.Audio, cameraGranted = cameraGranted, micGranted = true,
            ))
        }
    }

    @Test fun audioFailureWithoutMicPermissionRequestsPermission() {
        for (cameraGranted in listOf(false, true)) {
            assertEquals(Routes.ErrorMic, FlowRules.voiceCaptureFailureRoute(
                VoiceCaptureFailure.Audio, cameraGranted = cameraGranted, micGranted = false,
            ))
        }
    }

    @Test fun cameraFailureWithCameraPermissionOffersDeviceChecks() {
        for (micGranted in listOf(false, true)) {
            assertEquals(Routes.ErrorDevice, FlowRules.voiceCaptureFailureRoute(
                VoiceCaptureFailure.Camera, cameraGranted = true, micGranted = micGranted,
            ))
        }
    }

    @Test fun cameraFailureWithoutCameraPermissionRequestsPermission() {
        for (micGranted in listOf(false, true)) {
            assertEquals(Routes.ErrorCamera, FlowRules.voiceCaptureFailureRoute(
                VoiceCaptureFailure.Camera, cameraGranted = false, micGranted = micGranted,
            ))
        }
    }
}
