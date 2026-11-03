package vn.vericlue.app.screenshots

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.ui.screens.IdScanScreen
import vn.vericlue.app.ui.theme.VcTheme

abstract class IdAutomaticScanSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun prolongedScanKeepsAutomaticGuidanceWithoutAShutterButton() {
        var texts = emptyList<String>()
        paparazzi.snapshot("automatic_scan_after_wait") {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    texts = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                        .flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }
                        .map { it.text }
                }) {
                    IdScanScreen(false, IdQuality(500.0, 0.0,
                        "001095012345||NGUOI DUNG MINH HOA|01011995|Nam|Ha Noi|01012023",
                        portraitPresent = true), {}, {})
                }
            }
        }
        assertTrue("The user can still stop verification", "Dừng xác minh" in texts)
        assertFalse("Waiting must never expose a manual shutter", texts.any { "Chụp ảnh thẻ" in it })
        assertTrue("Automatic capture remains explained", texts.any { "đang tự chụp" in it })
    }
}

class CompactIdAutomaticScanSnapshotTest : IdAutomaticScanSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextIdAutomaticScanSnapshotTest : IdAutomaticScanSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
