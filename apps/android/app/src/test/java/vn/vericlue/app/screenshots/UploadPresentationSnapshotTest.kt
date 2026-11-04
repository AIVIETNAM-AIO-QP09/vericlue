package vn.vericlue.app.screenshots

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.theme.VcTheme

abstract class UploadPresentationSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    @Test fun uploadShowsOneIndeterminateStatusAndKeepsStopAvailable() {
        for (dark in listOf(false, true)) {
            var texts = emptyList<String>()
            var progress = emptyList<ProgressBarRangeInfo>()
            var completed = false
            paparazzi.snapshot("upload_$dark") {
                val root = LocalView.current as RootForTest
                VcTheme(dark = dark, motionEnabled = false) {
                    Box(Modifier.fillMaxSize().onGloballyPositioned {
                        val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                        texts = nodes.flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                        progress = nodes.mapNotNull { it.config.getOrNull(SemanticsProperties.ProgressBarRangeInfo) }
                    }) { Messages.Uploading({}, { completed = true }, auto = false) }
                }
            }
            assertTrue("Đang gửi dữ liệu" in texts)
            assertTrue("Dừng xác minh" in texts)
            assertTrue("Actual upload state has accessible indeterminate progress", progress == listOf(ProgressBarRangeInfo.Indeterminate))
            assertFalse("Never invent a transfer percentage", texts.any { '%' in it })
            assertFalse("Rendering cannot finish a live upload", completed)
        }
    }
}
class CompactUploadPresentationSnapshotTest : UploadPresentationSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextUploadPresentationSnapshotTest : UploadPresentationSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeUploadPresentationSnapshotTest : UploadPresentationSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
