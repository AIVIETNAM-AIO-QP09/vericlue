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
import vn.vericlue.app.ui.screens.DocumentCardScreen
import vn.vericlue.app.ui.screens.DocumentScanStage
import vn.vericlue.app.ui.theme.VcTheme

abstract class DocumentCardSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun unavailableScannerOffersRetryAndAnAlternativeWithoutLosingStop() {
        var texts = emptyList<String>()
        paparazzi.snapshot("document_scanner_unavailable") {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    texts = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                        .flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                }) {
                    DocumentCardScreen(DocumentScanStage.Failed,
                        "Chưa mở được bộ quét. Thử lại hoặc dùng camera của ứng dụng.", {}, {}, {}, {})
                }
            }
        }
        assertTrue("Quét lại thẻ" in texts)
        assertTrue("Dùng camera của ứng dụng" in texts)
        assertTrue("Dừng xác minh" in texts)
        assertFalse(texts.any { "Đã trích xuất" in it })
    }

    @Test fun readingDoesNotClaimSuccessfulExtractionOrOfferDuplicateUpload() {
        var texts = emptyList<String>()
        paparazzi.snapshot("document_scanner_reading") {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    texts = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                        .flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                }) {
                    DocumentCardScreen(DocumentScanStage.Reading, onBack = {}, onStop = {}, onRetry = {}, onFallback = {})
                }
            }
        }
        assertTrue("Đang đọc thông tin và chân dung" in texts)
        assertFalse("Quét lại thẻ" in texts)
        assertFalse(texts.any { "Đã trích xuất" in it })
    }
}

class CompactDocumentCardSnapshotTest : DocumentCardSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextDocumentCardSnapshotTest : DocumentCardSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
