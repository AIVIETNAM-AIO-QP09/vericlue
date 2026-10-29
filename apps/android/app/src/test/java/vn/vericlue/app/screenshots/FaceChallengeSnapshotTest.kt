package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.screens.FaceChallengeContent
import vn.vericlue.app.ui.theme.VcTheme

/** Both real and offline flows call this presentation; no camera or model is opened here. */
abstract class FaceChallengeSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun qrCardStates() {
        val q = vn.vericlue.app.capture.IdQuality(500.0, 0.0, null, portraitPresent = true)
        paparazzi.snapshot("card_auto") { VcTheme(motionEnabled = false) {
            vn.vericlue.app.ui.screens.IdScanScreen(false, q, {}, {}, {})
        } }
        paparazzi.snapshot("card_timeout") { VcTheme(motionEnabled = false) {
            vn.vericlue.app.ui.screens.IdScanScreen(true, q, {}, {}, {}, timedOut = true)
        } }
        paparazzi.snapshot("card_server_retry") { VcTheme(motionEnabled = false) {
            vn.vericlue.app.ui.screens.IdProcessingScreen({}, {}, vn.vericlue.app.capture.idScanErrorText("QR_UNREADABLE"))
        } }
    }

    @Test fun allFacePhases() {
        val timeline = FaceTimeline.demo(listOf(TurnDir.Left, TurnDir.Right))
        val phases = listOf(
            "baseline" to FaceTimeline.Phase.Colour(0),
            "colour" to FaceTimeline.Phase.Colour(2),
            "gaze" to FaceTimeline.Phase.Gaze(0.25, 0.55),
            "left" to FaceTimeline.Phase.Head(0, TurnDir.Left),
            "right" to FaceTimeline.Phase.Head(1, TurnDir.Right),
            "center" to FaceTimeline.Phase.Head(2, null),
        )
        for (dark in listOf(false, true)) {
            for ((name, phase) in phases) {
                paparazzi.snapshot("${name}_${if (dark) "dark" else "light"}") {
                    VcTheme(dark = dark, motionEnabled = false) {
                        FaceChallengeContent(timeline, phase) {}
                    }
                }
            }
        }
    }
}

class FaceChallengeSnapshotTest : FaceChallengeSnapshots(DeviceConfig.PIXEL_5)

class SmallFaceChallengeSnapshotTest : FaceChallengeSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextFaceChallengeSnapshotTest : FaceChallengeSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
