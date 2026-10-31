package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.ManualDemoCompleteScreen
import vn.vericlue.app.ui.theme.VcTheme

abstract class ManualDemoSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    @Test fun disclosureAndCompletion() {
        for (dark in listOf(false, true)) {
            paparazzi.snapshot("notice_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                FaceReadyScreen({}, {}, {}, manualDemo = true)
            } }
            paparazzi.snapshot("complete_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                ManualDemoCompleteScreen({})
            } }
        }
    }
}

class ManualDemoSnapshotTest : ManualDemoSnapshots(DeviceConfig.PIXEL_5)
class LargeTextManualDemoSnapshotTest : ManualDemoSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160,
    density = Density.MEDIUM, fontScale = 2f,
))
