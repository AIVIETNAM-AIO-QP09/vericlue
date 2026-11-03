package vn.vericlue.app.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.PersonOutline
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import vn.vericlue.app.flow.PrivacyNotice
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.ContentCard
import vn.vericlue.app.ui.components.IdentityScene3D
import vn.vericlue.app.ui.components.IllustrationScene
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.VcLogo
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Display data only. The authenticated API response owns identity and expiration. */
@Immutable
data class AccountHomeData(
    val fullName: String?,
    val username: String,
    val accountId: String,
    val maskedIdentityNumber: String? = null,
    val maskedPhone: String? = null,
    val createdAt: String,
    val expiresAt: String,
    val manualFullDemo: Boolean = false,
)

/** Password values live only in the caller's transient state; never save them in UI storage. */
@Composable
fun LoginScreen(
    username: String,
    password: String,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onPasswordLogin: () -> Unit,
    onFaceLogin: () -> Unit,
    onRegister: () -> Unit,
    onRecovery: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
    notice: String? = null,
    faceAvailable: Boolean = true,
    manualFullDemo: Boolean = false,
) {
    val focus = LocalFocusManager.current
    val submit = { focus.clearFocus(); onPasswordLogin() }
    AccessPage {
        AccessHero("TÀI KHOẢN VERICLUE", "Chào mừng trở lại", "Truy cập hồ sơ của bạn.")
        AccessPanel {
            AccessHeading("Đăng nhập")
            if (manualFullDemo) DemoAccessLabel()
            if (notice != null) AccessNotice(notice)
            if (error != null) AccessNotice(error, error = true)
            AccessTextField(username, onUsernameChange, "Tên đăng nhập", Icons.Outlined.PersonOutline,
                enabled = !busy, imeAction = ImeAction.Next)
            AccessPasswordField(password, onPasswordChange, "Mật khẩu", enabled = !busy,
                onDone = { if (username.isNotBlank() && password.isNotEmpty() && !busy) submit() })
            TextButton(onClick = onRecovery, enabled = !busy, modifier = Modifier.align(Alignment.End).heightIn(min = 48.dp)) {
                Text("Quên mật khẩu?", style = VcType.label)
            }
            PrimaryButton("Đăng nhập", submit, enabled = username.isNotBlank() && password.isNotEmpty(), loading = busy)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                HorizontalDivider(Modifier.weight(1f), color = Vc.colors.border)
                Text("hoặc", style = VcType.caption, color = Vc.colors.muted)
                HorizontalDivider(Modifier.weight(1f), color = Vc.colors.border)
            }
            AccessAction("Đăng nhập khuôn mặt", Icons.Outlined.Face, onFaceLogin, enabled = faceAvailable && !busy)
            if (!faceAvailable) Text("Đăng ký tài khoản trên thiết bị này để dùng đăng nhập khuôn mặt.",
                style = VcType.caption, color = Vc.colors.muted)
            HorizontalDivider(color = Vc.colors.border, modifier = Modifier.padding(top = 4.dp))
            Text("Bạn chưa có tài khoản?", style = VcType.bodySmall, color = Vc.colors.muted)
            AccessAction("Mở tài khoản", Icons.Outlined.Badge, onRegister, enabled = !busy)
        }
        Text("VeriClue · Danh tính của bạn", style = VcType.caption, color = Vc.colors.muted,
            modifier = Modifier.align(Alignment.CenterHorizontally).padding(vertical = 24.dp))
    }
}

@Composable
fun CredentialSetupScreen(
    username: String,
    password: String,
    confirmation: String,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onConfirmationChange: (String) -> Unit,
    profileConsent: Boolean,
    onProfileConsentChange: (Boolean) -> Unit,
    onSave: () -> Unit,
    onBack: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
    manualFullDemo: Boolean = false,
) {
    val focus = LocalFocusManager.current
    val canSave = username.isNotBlank() && password.isNotEmpty() && confirmation.isNotEmpty() && profileConsent
    AccessPage {
        AccessTopBar("Thiết lập đăng nhập", onBack, enabled = !busy)
        Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            AccessStatus("Danh tính đã được xác minh")
            AccessHeading("Một bước cuối để bắt đầu", large = true)
            Text("Tạo thông tin đăng nhập để truy cập hồ sơ mà không cần đăng ký lại.", style = VcType.body, color = Vc.colors.muted)
        }
        AccessPanel {
            if (manualFullDemo) DemoAccessLabel()
            if (error != null) AccessNotice(error, error = true)
            AccessTextField(username, onUsernameChange, "Tên đăng nhập", Icons.Outlined.PersonOutline,
                enabled = !busy, imeAction = ImeAction.Next,
                helper = "3–32 ký tự: chữ thường, số, dấu chấm, gạch dưới hoặc gạch ngang.")
            AccessPasswordField(password, onPasswordChange, "Mật khẩu", enabled = !busy,
                imeAction = ImeAction.Next, helper = "Từ 12 đến 128 ký tự. Nên dùng một cụm từ dễ nhớ.")
            AccessPasswordField(confirmation, onConfirmationChange, "Nhập lại mật khẩu", enabled = !busy,
                onDone = { if (canSave && !busy) { focus.clearFocus(); onSave() } })
            ConsentRow(profileConsent, onProfileConsentChange, enabled = !busy,
                text = "Tôi đồng ý lưu tên đăng nhập và hồ sơ gồm họ tên, thông tin định danh đã che bớt cùng thời hạn tài khoản, tối đa 24 giờ trong bản demo.")
            PrimaryButton("Lưu và đến đăng nhập", { focus.clearFocus(); onSave() }, enabled = canSave, loading = busy)
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
fun FaceLoginIntroScreen(
    onBack: () -> Unit,
    onStart: () -> Unit,
    consent: Boolean,
    onConsentChange: (Boolean) -> Unit,
    busy: Boolean = false,
    error: String? = null,
    manualFullDemo: Boolean = false,
) {
    var privacyExpanded by remember { mutableStateOf(false) }
    AccessPage {
        AccessTopBar("Đăng nhập khuôn mặt", onBack, enabled = !busy)
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            IdentityScene3D(Modifier.fillMaxWidth().height(128.dp), IllustrationScene.Face)
            AccessHeading("Nhìn vào camera để đăng nhập", large = true)
            Text("Đặt toàn bộ khuôn mặt trong khung và giữ điện thoại ổn định.",
                style = VcType.body, color = Vc.colors.muted)
            if (manualFullDemo) DemoAccessLabel()
            if (error != null) AccessNotice(error, error = true)
            ContentCard {
                Text("Xác minh phiên đăng nhập", style = VcType.section, color = Vc.colors.ink)
                Text("Thông báo ${PrivacyNotice.VERSION} · xử lý trong phiên", style = VcType.caption, color = Vc.colors.muted)
                ConsentRow(consent, onConsentChange, enabled = !busy,
                    text = "Tôi đồng ý xử lý khuôn mặt và giọng nói khi cần để xác minh phiên đăng nhập này.")
                TextButton(onClick = { privacyExpanded = !privacyExpanded }, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(if (privacyExpanded) "Thu gọn thông tin" else "Thông tin quyền riêng tư", style = VcType.label)
                }
                if (privacyExpanded) Text("Video khuôn mặt và bản ghi giọng nói khi cần được gửi đến máy chủ VeriClue để xác minh. Bạn có thể hủy trước khi bắt đầu hoặc dừng phiên để yêu cầu rút lại đồng ý. Thời hạn xử lý theo thông báo quyền riêng tư của phiên.",
                    style = VcType.bodySmall, color = Vc.colors.muted)
            }
            PrimaryButton("Bắt đầu quét", onStart, enabled = consent, loading = busy)
        }
    }
}

@Composable
fun AccountHomeScreen(
    profile: AccountHomeData,
    onLogout: () -> Unit,
    onPrivacy: () -> Unit,
    onRefresh: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
) {
    AccessPage {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            VcLogo(height = 24.dp)
            Spacer(Modifier.weight(1f))
            IconButton(onClick = onRefresh, enabled = !busy) {
                Icon(Icons.Outlined.Refresh, "Cập nhật hồ sơ", tint = Vc.colors.accent)
            }
        }
        Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            if (profile.manualFullDemo) DemoAccessLabel()
            if (error != null) AccessNotice(error, error = true)
            if (busy) AccessNotice("Đang cập nhật hồ sơ…")
            Surface(shape = RoundedCornerShape(28.dp), color = Vc.colors.surfaceInfo) {
                Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(Modifier.size(48.dp).background(Vc.colors.surface, CircleShape), contentAlignment = Alignment.Center) {
                            Icon(Icons.Outlined.AccountCircle, null, Modifier.size(30.dp), tint = Vc.colors.accent)
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("Xin chào,", style = VcType.bodySmall, color = Vc.colors.muted)
                            Text(profile.fullName?.takeIf(String::isNotBlank) ?: profile.username,
                                style = VcType.titleMedium, color = Vc.colors.ink, modifier = Modifier.semantics { heading() })
                        }
                    }
                    AccessStatus("Đã xác minh danh tính")
                    Text("Hồ sơ cá nhân của bạn", style = VcType.body, color = Vc.colors.ink)
                }
            }
            ContentCard {
                AccessHeading("Thông tin tài khoản")
                ProfileValue("Tên đăng nhập", profile.username)
                profile.fullName?.takeIf(String::isNotBlank)?.let { ProfileValue("Họ và tên", it) }
                profile.maskedIdentityNumber?.takeIf(String::isNotBlank)?.let { ProfileValue("Số định danh", it) }
                profile.maskedPhone?.takeIf(String::isNotBlank)?.let { ProfileValue("Số điện thoại", it) }
                ProfileValue("Mã tài khoản", profile.accountId)
            }
            ContentCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(Icons.Outlined.Shield, null, tint = Vc.colors.accent)
                    AccessHeading("Bảo mật và quyền riêng tư")
                }
                Text("Đăng nhập bằng mật khẩu hoặc khuôn mặt VeriClue trên thiết bị đã đăng ký.", style = VcType.bodySmall, color = Vc.colors.muted)
                ProfileValue("Ngày tạo", profile.createdAt)
                ProfileValue("Có hiệu lực đến", profile.expiresAt)
                if (profile.manualFullDemo) Text("Tài khoản thử nghiệm có thời hạn tối đa 24 giờ. Hết hạn, bạn cần đăng ký lại.",
                    style = VcType.caption, color = Vc.colors.muted)
                AccessAction("Quyền riêng tư", Icons.Outlined.Info, onPrivacy, enabled = !busy)
            }
            AccessAction("Đăng xuất", Icons.AutoMirrored.Outlined.Logout, onLogout, enabled = !busy)
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun AccessPage(content: @Composable ColumnScope.() -> Unit) {
    val motion = Vc.motion
    val appear = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) { appear.animateTo(1f, motion.tween(280)) }
    SystemBarIcons(Vc.colors.background)
    Box(Modifier.fillMaxSize().background(Vc.colors.background).statusBarsPadding().imePadding(), contentAlignment = Alignment.TopCenter) {
        Column(Modifier.widthIn(max = 600.dp).fillMaxWidth().verticalScroll(rememberScrollState())
            .navigationBarsPadding().alpha(appear.value), content = content)
    }
}

@Composable
private fun AccessHero(eyebrow: String, title: String, subtitle: String) {
    val color = Vc.colors.illustration
    val largeText = LocalDensity.current.fontScale >= 1.5f
    Box(Modifier.fillMaxWidth()) {
        Canvas(Modifier.matchParentSize().clearAndSetSemantics {}) {
            drawCircle(color, radius = size.width * .45f, center = androidx.compose.ui.geometry.Offset(size.width * .96f, size.height * .30f))
            drawCircle(color, radius = size.width * .56f, center = androidx.compose.ui.geometry.Offset(size.width * .96f, size.height * .30f), style = Stroke(1.dp.toPx()))
        }
        Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            VcLogo(height = 26.dp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(eyebrow, style = VcType.labelXs, color = Vc.colors.accent)
                    AccessHeading(title, large = true)
                    Text(subtitle, style = VcType.bodySmall, color = Vc.colors.muted)
                }
                if (!largeText) IdentityScene3D(Modifier.width(128.dp).height(132.dp), IllustrationScene.Privacy)
            }
        }
    }
}

@Composable
private fun AccessPanel(content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
        color = Vc.colors.surface, shape = RoundedCornerShape(28.dp), border = BorderStroke(1.dp, Vc.colors.border)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
private fun AccessTopBar(title: String, onBack: () -> Unit, enabled: Boolean) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onBack, enabled = enabled) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Quay lại", tint = Vc.colors.ink) }
        Text(title, style = VcType.section, color = Vc.colors.ink, modifier = Modifier.weight(1f).semantics { heading() })
    }
}

@Composable
private fun AccessHeading(text: String, large: Boolean = false) {
    Text(text, style = if (large) VcType.titleLarge else VcType.section, color = Vc.colors.ink, modifier = Modifier.semantics { heading() })
}

@Composable
private fun DemoAccessLabel() {
    Banner("Demo · Ngưỡng chưa hiệu chỉnh", tone = Tone.Warn)
}

@Composable
private fun AccessNotice(text: String, error: Boolean = false) {
    Banner(text, tone = if (error) Tone.Warn else Tone.Info,
        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
}

@Composable
private fun AccessStatus(text: String) {
    Row(Modifier.background(Vc.colors.okBg, RoundedCornerShape(14.dp)).padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(Icons.Outlined.CheckCircle, null, tint = Vc.colors.ok, modifier = Modifier.size(18.dp))
        Text(text, style = VcType.labelSmall, color = Vc.colors.ok)
    }
}

@Composable
private fun AccessTextField(
    value: String, onChange: (String) -> Unit, label: String, icon: ImageVector,
    enabled: Boolean, imeAction: ImeAction = ImeAction.Done, helper: String? = null,
) {
    val focus = LocalFocusManager.current
    OutlinedTextField(value = value, onValueChange = onChange, enabled = enabled,
        modifier = Modifier.fillMaxWidth(), label = { Text(label, style = VcType.bodySmall) },
        textStyle = VcType.body, singleLine = true, shape = RoundedCornerShape(16.dp),
        leadingIcon = { Icon(icon, null) },
        supportingText = helper?.let { { Text(it, style = VcType.caption) } },
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Ascii, imeAction = imeAction),
        keyboardActions = KeyboardActions(onNext = { focus.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }))
}

@Composable
private fun AccessPasswordField(
    value: String, onChange: (String) -> Unit, label: String, enabled: Boolean,
    imeAction: ImeAction = ImeAction.Done, helper: String? = null, onDone: () -> Unit = {},
) {
    var visible by remember { mutableStateOf(false) }
    val focus = LocalFocusManager.current
    OutlinedTextField(value = value, onValueChange = onChange, enabled = enabled,
        modifier = Modifier.fillMaxWidth(), label = { Text(label, style = VcType.bodySmall) },
        textStyle = VcType.body, singleLine = true, shape = RoundedCornerShape(16.dp),
        leadingIcon = { Icon(Icons.Outlined.Lock, null) },
        supportingText = helper?.let { { Text(it, style = VcType.caption) } },
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        trailingIcon = { IconButton(onClick = { visible = !visible }, enabled = enabled) {
            Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                if (visible) "Ẩn $label" else "Hiện $label")
        } },
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password, imeAction = imeAction),
        keyboardActions = KeyboardActions(onDone = { onDone() }, onNext = { focus.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }))
}

@Composable
private fun ConsentRow(checked: Boolean, onChecked: (Boolean) -> Unit, enabled: Boolean, text: String) {
    Row(Modifier.fillMaxWidth().toggleable(value = checked, enabled = enabled, role = Role.Checkbox, onValueChange = onChecked)
        .padding(vertical = 6.dp), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Checkbox(checked, onCheckedChange = null, enabled = enabled, modifier = Modifier.size(48.dp))
        Text(text, style = VcType.bodySmall, color = Vc.colors.ink, modifier = Modifier.weight(1f).padding(top = 12.dp, bottom = 8.dp))
    }
}

@Composable
private fun AccessAction(text: String, icon: ImageVector, onClick: () -> Unit, enabled: Boolean = true) {
    OutlinedButton(onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, Vc.colors.border)) {
        Icon(icon, null, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(10.dp))
        Text(text, style = VcType.button, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun ProfileValue(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, style = VcType.caption, color = Vc.colors.muted)
        Text(value, style = VcType.bodyStrong, color = Vc.colors.ink)
    }
}
