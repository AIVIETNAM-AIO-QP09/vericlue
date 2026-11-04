package vn.vericlue.app.screenshots

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
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
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.AccountHomeData
import vn.vericlue.app.ui.screens.AccountHomeScreen
import vn.vericlue.app.ui.screens.CredentialSetupScreen
import vn.vericlue.app.ui.screens.FaceLoginIntroScreen
import vn.vericlue.app.ui.screens.LoginScreen
import vn.vericlue.app.ui.theme.VcTheme

/** Synthetic profile only; verifies the real Compose layout and disclosure states. */
abstract class AccountAccessSnapshots(private val device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    private val noop: () -> Unit = {}
    private val edit: (String) -> Unit = {}
    private var texts = emptyList<String>()
    private var passwords = 0
    private var disabledActions = emptySet<String>()
    private var textBounds = emptyMap<String, Rect>()
    private var canScroll = false

    private fun shot(name: String, dark: Boolean, content: @Composable () -> Unit) {
        texts = emptyList()
        passwords = 0
        disabledActions = emptySet()
        textBounds = emptyMap()
        canScroll = false
        paparazzi.snapshot("${name}_$dark") {
            val root = LocalView.current as RootForTest
            VcTheme(dark = dark, motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                    texts = nodes.flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                    passwords = nodes.count { it.config.contains(SemanticsProperties.Password) }
                    textBounds = nodes.flatMap { node -> node.config.getOrNull(SemanticsProperties.Text).orEmpty()
                        .map { it.text to node.boundsInRoot } }.toMap()
                    canScroll = nodes.any { (it.config.getOrNull(SemanticsProperties.VerticalScrollAxisRange)?.maxValue?.invoke() ?: 0f) > 0f }
                    disabledActions = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = true)
                        .filter { it.config.contains(SemanticsProperties.Disabled) }
                        .flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }.toSet()
                }) { content() }
            }
        }
    }

    @Test fun firstLaunchMakesAccountCreationDiscoverableWithoutAnExistingFaceBinding() {
        for (dark in listOf(false, true)) {
            shot("login_first_launch", dark) {
                LoginScreen("", "", edit, edit, noop, noop, noop, noop, faceAvailable = false)
            }
            assertTrue("Unbound devices cannot start face login", "Đăng nhập khuôn mặt" in disabledActions)
            assertFalse("New account creation stays available", "Mở tài khoản" in disabledActions)
            if (device.fontScale < 1.5f) {
                val register = requireNotNull(textBounds["Mở tài khoản"])
                assertTrue("Account creation should be visible at default text size", register.height >= 20f && register.bottom <= device.screenHeight)
            } else {
                assertTrue("Large text can scroll to all actions", canScroll)
            }
        }
    }

    @Test fun loginKeepsPasswordProtectedAndOffersBothMethods() {
        for (dark in listOf(false, true)) {
            shot("login", dark) {
                LoginScreen("nguoidung.demo", "Synthetic passphrase", edit, edit, noop, noop, noop, noop,
                    manualFullDemo = true)
            }
            assertTrue("Password must have native password semantics", passwords > 0)
            assertTrue("Đăng nhập khuôn mặt" in texts)
            assertTrue("Mở tài khoản" in texts)
            assertTrue("Demo · Ngưỡng chưa hiệu chỉnh" in texts)
            assertFalse(texts.any { it == "Số dư" || it == "0123 4567 8901" })
        }
    }

    @Test fun setupExplainsExplicitProfileConsentWithoutClaimingItWasSaved() {
        for (dark in listOf(false, true)) {
            shot("setup", dark) {
                CredentialSetupScreen("nguoidung.demo", "", "", edit, edit, edit,
                    profileConsent = false, onProfileConsentChange = {}, onSave = noop, onBack = noop,
                    manualFullDemo = true)
            }
            assertTrue(texts.any { it.contains("Tôi đồng ý lưu") && it.contains("24 giờ") })
            assertTrue("Lưu và đến đăng nhập" in texts)
            assertTrue("Saving requires explicit profile consent", "Lưu và đến đăng nhập" in disabledActions)
            assertFalse("Đã lưu hồ sơ" in texts)
        }
    }

    @Test fun faceEntryAsksForProcessingConsentAndDoesNotPromiseInstantSuccess() {
        for (dark in listOf(false, true)) {
            shot("face_entry", dark) {
                FaceLoginIntroScreen(noop, noop, consent = false, onConsentChange = {}, manualFullDemo = true)
            }
            assertTrue("Bắt đầu quét" in texts)
            assertTrue("Capture cannot begin before consent", "Bắt đầu quét" in disabledActions)
            assertTrue(texts.any { it.contains("Tôi đồng ý xử lý khuôn mặt") })
            assertFalse(texts.any { "3 giây" in it || "Face ID" in it })
        }
    }

    @Test fun homeUsesOnlySuppliedProfileAndRetainsDemoDisclosure() {
        val profile = AccountHomeData(
            fullName = "NGƯỜI DÙNG MINH HỌA", username = "nguoidung.demo",
            accountId = "acct_synthetic_example", maskedIdentityNumber = "••••••••1234",
            createdAt = "03/11/2026 · 18:30", expiresAt = "04/11/2026 · 18:30", manualFullDemo = true,
        )
        for (dark in listOf(false, true)) {
            shot("account_home", dark) { AccountHomeScreen(profile, noop, noop, noop) }
            assertTrue(profile.accountId in texts)
            assertTrue(profile.maskedIdentityNumber in texts)
            assertEquals("No fabricated phone when API omitted it", 0, texts.count { it == "Số điện thoại" })
            assertTrue("Demo · Ngưỡng chưa hiệu chỉnh" in texts)
            assertFalse(texts.any { it == "Số dư" || it == "Dữ liệu mẫu" || it == "0123 4567 8901" })
        }
    }
}

class AccountAccessSnapshotTest : AccountAccessSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextAccountAccessSnapshotTest : AccountAccessSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
