package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.ManualDemoCompleteScreen
import vn.vericlue.app.ui.screens.SuccessScreen
import vn.vericlue.app.ui.screens.BankOpenedScreen
import vn.vericlue.app.ui.screens.BankStartScreen
import vn.vericlue.app.ui.screens.AuthScreen
import vn.vericlue.app.flow.Purpose
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
    @Test fun accountCompletionAndRestoredEntryKeepTheDemoLabel() {
        for (dark in listOf(false, true)) {
            for (purpose in Purpose.entries) {
                paparazzi.snapshot("account_${purpose}_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                    SuccessScreen(purpose, {}, manualFullDemo = true, accountReady = true)
                } }
            }
            paparazzi.snapshot("bank_complete_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                BankOpenedScreen({}, manualFullDemo = true)
            } }
            paparazzi.snapshot("restored_bank_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                BankStartScreen({}, {}, manualFullDemo = true)
            } }
            paparazzi.snapshot("restored_auth_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                AuthScreen({}, {}, {}, manualFullDemo = true)
            } }
            paparazzi.snapshot("offline_preview_$dark") { VcTheme(dark = dark, motionEnabled = false) {
                SuccessScreen(Purpose.Onboarding, {}, preview = true)
            } }
        }
    }
}

class ManualDemoSnapshotTest : ManualDemoSnapshots(DeviceConfig.PIXEL_5)
class LargeTextManualDemoSnapshotTest : ManualDemoSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160,
    density = Density.MEDIUM, fontScale = 2f,
))
