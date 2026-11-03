package vn.vericlue.app.screenshots

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.QuickFaceLoginContent
import vn.vericlue.app.ui.screens.QuickFaceStage
import vn.vericlue.app.ui.theme.VcTheme

abstract class QuickFaceLoginSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun onePreviewNoOvalAndNoSuccessBeforeServerResult() {
        for (dark in listOf(false, true)) {
            var bounds: Rect? = null
            for (stage in QuickFaceStage.entries) {
                var preview: Rect? = null
                var text = emptyList<String>()
                var tags = emptyList<String>()
                paparazzi.snapshot("quick_${stage}_$dark") {
                    val root = LocalView.current as RootForTest
                    VcTheme(dark = dark, motionEnabled = false) {
                        Box(Modifier.fillMaxSize().onGloballyPositioned {
                            val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            tags = nodes.mapNotNull { it.config.getOrNull(SemanticsProperties.TestTag) }
                            preview = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "quick-face-preview" }?.boundsInRoot
                            text = nodes.flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                        }) {
                            QuickFaceLoginContent(stage, "Nhìn thẳng vào camera", {}, {})
                        }
                    }
                }
                if (bounds == null) bounds = requireNotNull(preview)
                assertEquals("Preview must not resize or move between capture phases", bounds, preview)
                assertFalse("No oval placement step in quick login", "face-guide" in tags)
                assertFalse(text.any { it.contains("thành công", true) || it.startsWith("Bước") })
                assertTrue("Cancellation remains available while the server runs", "Hủy" in text)
                if (stage == QuickFaceStage.Consent) {
                    assertTrue(text.any { it.contains("xử lý khuôn mặt và giọng nói") })
                    assertTrue("Explicit consent precedes capture", "Đồng ý và quét" in text)
                } else assertFalse("Consent is not repeated as a separate screen", "Đồng ý và quét" in text)
                if (stage == QuickFaceStage.Checking) assertTrue("Đang xác minh…" in text)
            }
        }
    }
}

class QuickFaceLoginSnapshotTest : QuickFaceLoginSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextQuickFaceLoginSnapshotTest : QuickFaceLoginSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
