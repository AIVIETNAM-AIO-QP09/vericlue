package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.ui.screens.TermsScreen
import vn.vericlue.app.ui.screens.SuccessScreen
import vn.vericlue.app.ui.theme.VcTheme

abstract class TermsSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun consentAndExperimentalResult() {
        for (dark in listOf(false, true)) {
            for (purpose in Purpose.entries) {
                paparazzi.snapshot("${purpose}_$dark") {
                    VcTheme(dark = dark, motionEnabled = false) {
                        TermsScreen({}, {}, purpose = purpose)
                    }
                }
            }
            paparazzi.snapshot("manual_full_success_$dark") {
                VcTheme(dark = dark, motionEnabled = false) {
                    SuccessScreen(Purpose.Onboarding, {}, auto = false, manualFullDemo = true)
                }
            }
        }
    }
}

class TermsSnapshotTest : TermsSnapshots(DeviceConfig.PIXEL_5)
class LargeTextTermsSnapshotTest : TermsSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160,
    density = Density.MEDIUM, fontScale = 2f,
))
