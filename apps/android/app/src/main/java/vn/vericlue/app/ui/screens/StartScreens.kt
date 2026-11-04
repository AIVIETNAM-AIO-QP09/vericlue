package vn.vericlue.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.KeyboardArrowUp
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import vn.vericlue.app.BuildConfig
import vn.vericlue.app.R
import vn.vericlue.app.flow.Agreement
import vn.vericlue.app.ui.components.ChecklistCard
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.ContentCard
import vn.vericlue.app.ui.components.WelcomePanel
import vn.vericlue.app.ui.components.JourneyOverview
import vn.vericlue.app.ui.components.HelpButton
import vn.vericlue.app.ui.components.FeatureRow
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.IdentityIllustration
import vn.vericlue.app.ui.components.IdentityScene3D
import vn.vericlue.app.ui.components.IllustrationScene
import vn.vericlue.app.ui.components.NumberedRow
import vn.vericlue.app.ui.components.SampleAccount
import vn.vericlue.app.ui.components.SuccessBadge
import vn.vericlue.app.ui.components.SecondaryButton
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.VcLogo
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.components.LivenessRing
import vn.vericlue.app.ui.components.StageAmbient
import vn.vericlue.app.ui.components.stageBackground
import vn.vericlue.app.ui.components.StatusBadge
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcStage
import vn.vericlue.app.ui.theme.VcType

// ── Host bank app (mock) ──────────────────────────────────────────────────────

@Composable
private fun BankHeader() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Icon(Icons.Outlined.AccountBalance, contentDescription = null, tint = Vc.colors.accent, modifier = Modifier.size(24.dp))
        Text("Ngân hàng Mẫu", style = VcType.label, color = Vc.colors.bankAccent)
    }
}

/** Mock of the bank app that opens VeriClue. Not part of VeriClue itself. */
@Composable
fun BankStartScreen(onOpenAccount: () -> Unit, onGallery: () -> Unit, manualFullDemo: Boolean = false, preview: Boolean = false) {
    VcScreen(showLogo = false, actions = {
        PrimaryButton("Mở tài khoản", onOpenAccount)
        if (BuildConfig.DEBUG) LinkButton("Xem tất cả màn (bản demo giao diện)", onGallery)
    }) {
        BankHeader()
        if (preview) Banner("Xem trước giao diện · Không chạy AI", tone = Tone.Warn)
        IdentityIllustration(Modifier.height(230.dp))
        TitleBlock("Mở tài khoản trực tuyến", "Xác minh bằng thẻ căn cước và khuôn mặt.")
    }
}

@Composable
fun BankOpenedScreen(onDone: () -> Unit, manualFullDemo: Boolean = false, preview: Boolean = false) {
    VcScreen(centered = true, actions = { PrimaryButton("Vào ứng dụng", onDone) }) {
        SuccessBadge()
        TitleBlock(if (preview) "Xem trước màn hoàn tất" else "Tài khoản đã sẵn sàng",
            "Đăng nhập để xem hồ sơ và quản lý tài khoản của bạn.", centered = true)
        if (preview) Banner("Xem trước giao diện · Không chạy AI", tone = Tone.Warn)
    }
}

// ── Splash ────────────────────────────────────────────────────────────────────

@Composable
private fun Rings(color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val center = Offset(size.width / 2f, size.height / 2f)
        listOf(0.28f, 0.42f, 0.58f).forEach { r ->
            drawCircle(color, radius = size.width * r, center = center, style = Stroke(1.dp.toPx()))
        }
    }
}

@Composable
fun SplashScreen(onDone: () -> Unit) {
    val c = Vc.colors
    val motion = Vc.motion
    val appear = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) {
        appear.animateTo(1f, motion.tween(700))
        delay(900)
        onDone()
    }
    SystemBarIcons(c.background)
    Box(Modifier.fillMaxSize().stageBackground(), contentAlignment = Alignment.Center) {
        StageAmbient()
        Rings(c.illustration.copy(alpha = appear.value), Modifier.fillMaxSize())
        // The liveness ring draws itself around the mark while the app starts.
        Box(Modifier.alpha(appear.value)) {
            LivenessRing(active = true, size = 260.dp, arc = VcStage.ring, tick = c.border, disc = Color.Transparent,
                glow = c.accent) {}
        }
        Column(
            Modifier.alpha(appear.value).scale(0.92f + 0.08f * appear.value),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            VcLogo(height = 52.dp)
            Text("Xác minh danh tính", style = VcType.bodySmall, color = c.ink)
        }
        Column(
            Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 48.dp).alpha(appear.value),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (!motion.enabled) LinearProgressIndicator(
                progress = { 0.6f }, modifier = Modifier.width(120.dp).height(3.dp).clip(RoundedCornerShape(2.dp)),
                color = c.primary, trackColor = c.border,
            ) else LinearProgressIndicator(
                modifier = Modifier.width(120.dp).height(3.dp).clip(RoundedCornerShape(2.dp)),
                color = c.primary,
                trackColor = c.border,
            )
            Text("Đang khởi động…", style = VcType.caption, color = c.muted)
        }
    }
}

// ── Sign in / sign up ─────────────────────────────────────────────────────────

@Composable
fun AuthScreen(onRegister: () -> Unit, onLogin: () -> Unit, onRecover: () -> Unit, manualFullDemo: Boolean = false, preview: Boolean = false, onBack: (() -> Unit)? = null) {
    val c = Vc.colors
    VcScreen(onBack = onBack, actions = {
        PrimaryButton("Bắt đầu đăng ký", onRegister)
        LinkButton("Đã có tài khoản? Đăng nhập", onLogin)
    }) {
        if (preview) Banner("Xem trước giao diện · Không chạy AI", tone = Tone.Warn)
        WelcomePanel()
        ContentCard {
            Text("Hành trình xác minh", style = VcType.section, color = c.ink)
            JourneyOverview()
            HelpButton()
        }
    }
}

// ── Full notice followed by explicit, independent consent choices ──────────

private val dataUseDetails = listOf(
    "Mục đích sử dụng" to "Thông tin được dùng để đối chiếu danh tính và xử lý yêu cầu xác minh của bạn. Dữ liệu xác minh không được dùng để huấn luyện AI.",
    "Ảnh và giọng nói" to "Ứng dụng sử dụng ảnh thẻ và video khuôn mặt để xác minh. Giọng nói chỉ được thu khi bạn được yêu cầu đọc một câu bổ sung.",
    "Mẫu khuôn mặt" to "Đồng ý xử lý trong phiên không thay thế lựa chọn lưu mẫu tài khoản. Mẫu tài khoản chỉ được tạo khi có đủ điều kiện và quyền lưu mẫu riêng.",
    "Quyền chủ động" to "Camera và micro chỉ được sử dụng sau khi bạn cấp quyền. Bạn có thể dừng xác minh thay vì tiếp tục cung cấp dữ liệu.",
    "Kết quả xác minh" to "Kết quả xác minh không thay thế quyết định mở tài khoản của đơn vị cung cấp dịch vụ.",
)

/** Reaching the end unlocks the choices; scrolling never implies acceptance. */
@Composable
fun TermsScreen(
    onBack: () -> Unit,
    onAccept: () -> Unit,
    initialAccepted: Boolean = false,
    purpose: vn.vericlue.app.flow.Purpose = vn.vericlue.app.flow.Purpose.Onboarding,
    busy: Boolean = false,
    error: String? = null,
) {
    val c = Vc.colors
    var agreement by remember(purpose, initialAccepted) {
        mutableStateOf(
            Agreement(
                accepted = initialAccepted,
                accountTemplateAccepted = initialAccepted,
                requiresAccountTemplate = purpose == vn.vericlue.app.flow.Purpose.Onboarding,
            ),
        )
    }
    val scroll = remember(purpose) { ScrollState(0) }
    var readToEnd by remember(purpose) { mutableStateOf(false) }
    LaunchedEffect(scroll) {
        snapshotFlow { scroll.maxValue != Int.MAX_VALUE && !scroll.canScrollForward }
            .collect { atEnd -> if (atEnd) readToEnd = true }
    }
    val canChoose = readToEnd && !busy
    VcScreen(
        onBack = onBack,
        scrollState = scroll,
        actions = { PrimaryButton(if (busy) "Đang ghi nhận…" else "Đồng ý và tiếp tục", onAccept, enabled = readToEnd && agreement.canContinue && !busy) },
    ) {
        TitleBlock("Đồng ý xác minh", "Tìm hiểu cách VeriClue sử dụng thông tin của bạn.", eyebrow = "QUYỀN RIÊNG TƯ")
        ContentCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Thông tin cần sử dụng", style = VcType.section, color = c.ink, modifier = Modifier.weight(0.6f))
                IdentityScene3D(Modifier.weight(0.4f).height(100.dp), IllustrationScene.Privacy)
            }
            if (purpose != vn.vericlue.app.flow.Purpose.Reauth) DataUseRow(Icons.Outlined.Phone, "Số điện thoại")
            if (purpose == vn.vericlue.app.flow.Purpose.Onboarding) DataUseRow(Icons.Outlined.Badge, "Thông tin và chân dung trên thẻ")
            DataUseRow(Icons.Outlined.Face, if (purpose == vn.vericlue.app.flow.Purpose.Onboarding) "Ảnh và video khuôn mặt" else "Video khuôn mặt và đối chiếu mẫu tài khoản")
            DataUseRow(Icons.Outlined.Mic, "Giọng nói khi cần xác minh bổ sung")
        }
        ContentCard {
            Text("Thông tin xử lý dữ liệu", style = VcType.section, color = c.ink)
            dataUseDetails.forEach { (title, body) ->
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(title, style = VcType.label, color = c.ink)
                    Text(body, style = VcType.bodySmall, color = c.muted)
                }
            }
            if (purpose == vn.vericlue.app.flow.Purpose.Onboarding) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Lưu mẫu tài khoản trong 24 giờ", style = VcType.label, color = c.ink)
                    Text("Mẫu khuôn mặt được mã hóa và lưu trên máy chủ trong 24 giờ để đối chiếu khi đăng nhập lại hoặc khôi phục tài khoản. Dừng phiên xác minh không tự xóa tài khoản đã tạo.",
                        style = VcType.bodySmall, color = c.muted)
                }
            }
        }
        error?.let { Text(it, style = VcType.bodySmall, color = c.ink) }
        Text(if (readToEnd) "Chọn các mục bên dưới để tiếp tục." else "Cuộn đến cuối để mở lựa chọn đồng ý.",
            style = VcType.caption, color = c.muted)
        ConsentChoice(agreement.accepted, { agreement = agreement.toggle() }, enabled = canChoose,
            text = "Tôi đồng ý để VeriClue xử lý các thông tin trên nhằm xác minh danh tính.")
        if (purpose == vn.vericlue.app.flow.Purpose.Onboarding) {
            ConsentChoice(agreement.accountTemplateAccepted, { agreement = agreement.toggleAccountTemplate() }, enabled = canChoose,
                text = "Tôi đồng ý lưu mẫu khuôn mặt mã hóa trong 24 giờ để đăng nhập lại hoặc khôi phục tài khoản.")
        }
    }
}

@Composable
private fun DataUseRow(icon: ImageVector, title: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = Vc.colors.accent, modifier = Modifier.size(24.dp))
        Text(title, style = VcType.body, color = Vc.colors.ink)
    }
}

@Composable
private fun ConsentChoice(accepted: Boolean, onToggle: () -> Unit, enabled: Boolean, text: String) {
    val c = Vc.colors
    Row(
        Modifier.fillMaxWidth().heightIn(min = 48.dp).clip(RoundedCornerShape(16.dp))
            .background(if (accepted) c.surfaceInfo else c.surfaceSubtle)
            .border(1.dp, if (accepted) c.accent else c.border, RoundedCornerShape(16.dp))
            .toggleable(value = accepted, role = Role.Checkbox, enabled = enabled, onValueChange = { onToggle() })
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(Modifier.padding(top = 1.dp).size(22.dp).clip(CircleShape)
            .background(if (accepted) c.accent else Color.Transparent)
            .border(1.5.dp, if (accepted) c.accent else c.muted, CircleShape), contentAlignment = Alignment.Center) {
            if (accepted) Icon(Icons.Outlined.Check, contentDescription = null, tint = c.onPrimary, modifier = Modifier.size(16.dp))
        }
        Text(text, style = VcType.caption, color = if (enabled) c.ink else c.muted, modifier = Modifier.weight(1f))
    }
}
