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
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.vericlue.app.BuildConfig
import vn.vericlue.app.R
import vn.vericlue.app.flow.Agreement
import vn.vericlue.app.ui.components.ChecklistCard
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.IdentityIllustration
import vn.vericlue.app.ui.components.NumberedRow
import vn.vericlue.app.ui.components.SampleAccount
import vn.vericlue.app.ui.components.SuccessBadge
import vn.vericlue.app.ui.components.SecondaryButton
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.VcLogo
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.components.StatusBadge
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
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
fun BankStartScreen(onOpenAccount: () -> Unit, onGallery: () -> Unit) {
    VcScreen(showLogo = false, actions = {
        PrimaryButton("Mở tài khoản", onOpenAccount)
        if (BuildConfig.DEBUG) LinkButton("Xem tất cả màn (bản demo giao diện)", onGallery)
    }) {
        BankHeader()
        IdentityIllustration(Modifier.height(230.dp))
        TitleBlock("Mở tài khoản trực tuyến", "Xác minh bằng thẻ căn cước và khuôn mặt.")
    }
}

@Composable
fun BankOpenedScreen(onDone: () -> Unit) {
    VcScreen(actions = { SampleAccount(); PrimaryButton("Vào ứng dụng", onDone) }) {
        BankHeader()
        Spacer(Modifier.height(56.dp))
        SuccessBadge()
        TitleBlock("Đã hoàn tất xác minh")
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
    Box(Modifier.fillMaxSize().background(c.background), contentAlignment = Alignment.Center) {
        Rings(c.illustration.copy(alpha = appear.value), Modifier.fillMaxSize())
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
fun AuthScreen(onRegister: () -> Unit, onLogin: () -> Unit, onRecover: () -> Unit) {
    val c = Vc.colors
    val phase = if (Vc.motion.enabled) {
        val float = rememberInfiniteTransition(label = "float")
        val value by float.animateFloat(
            initialValue = -1f, targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(2400, easing = LinearEasing), RepeatMode.Reverse), label = "phase",
        )
        value
    } else 0f
    VcScreen(actions = {
        PrimaryButton("Đăng ký", onRegister)
        SecondaryButton("Đăng nhập", onLogin)
        LinkButton("Khôi phục tài khoản", onRecover)
    }) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            IdentityIllustration(Modifier.height(200.dp), phase)
            TitleBlock(
                "Xác minh danh tính",
                "Chuẩn bị thẻ căn cước và chọn nơi đủ sáng.",
            )
            Column {
                NumberedRow(1, "Thẻ căn cước")
                NumberedRow(2, "Khuôn mặt")
                NumberedRow(3, "Đọc một câu", detail = "Chỉ khi cần", last = true)
            }
        }
    }
}

// ── Explicit consent with expandable details ─────────────────────────────

private val dataUseDetails = listOf(
    "Mục đích sử dụng" to "Thông tin được dùng để đối chiếu danh tính và xử lý yêu cầu xác minh của bạn. Dữ liệu xác minh không được dùng để huấn luyện AI.",
    "Ảnh và giọng nói" to "Ứng dụng sử dụng ảnh thẻ và video khuôn mặt để xác minh. Giọng nói chỉ được thu khi bạn được yêu cầu đọc một câu bổ sung.",
    "Mẫu khuôn mặt" to "Khi đăng ký tài khoản, mẫu khuôn mặt được lưu ở dạng mã hóa để xác minh cho các lần truy cập sau.",
    "Quyền chủ động" to "Camera và micro chỉ được sử dụng sau khi bạn cấp quyền. Bạn có thể dừng xác minh thay vì tiếp tục cung cấp dữ liệu.",
    "Phạm vi thử nghiệm" to "Đây là bản thử nghiệm VeriClue. Kết quả xác minh không thay thế quyết định mở tài khoản của đơn vị cung cấp dịch vụ.",
)

/** Consent is explicit; expanding details or scrolling never implies acceptance. */
@Composable
fun TermsScreen(
    onBack: () -> Unit,
    onAccept: () -> Unit,
    initialAccepted: Boolean = false,
    initialDetailsOpen: Boolean = false,
) {
    val c = Vc.colors
    var agreement by remember { mutableStateOf(Agreement(accepted = initialAccepted)) }
    var detailsOpen by remember { mutableStateOf(initialDetailsOpen) }
    VcScreen(
        onBack = onBack,
        actions = { PrimaryButton("Đồng ý và tiếp tục", onAccept, enabled = agreement.canContinue) },
    ) {
        TitleBlock("Đồng ý xác minh")
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp))
                .background(c.surface).border(1.dp, c.border, RoundedCornerShape(16.dp))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Thông tin cần sử dụng", style = VcType.label, color = c.ink)
            DataUseRow(Icons.Outlined.Phone, "Số điện thoại")
            DataUseRow(Icons.Outlined.Badge, "Thông tin và chân dung trên thẻ")
            DataUseRow(Icons.Outlined.Face, "Ảnh, video và mẫu khuôn mặt mã hóa")
            DataUseRow(Icons.Outlined.Mic, "Giọng nói khi cần xác minh bổ sung")
        }
        LinkButton(
            if (detailsOpen) "Thu gọn thông tin xử lý dữ liệu" else "Xem chi tiết xử lý dữ liệu",
            onClick = { detailsOpen = !detailsOpen },
        )
        if (detailsOpen) {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                dataUseDetails.forEach { (title, body) ->
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(title, style = VcType.labelSmall, color = c.ink)
                        Text(body, style = VcType.body, color = c.ink)
                    }
                }
            }
        }
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                .background(if (agreement.accepted) c.surfaceInfo else c.surface)
                .toggleable(value = agreement.accepted, role = Role.Checkbox,
                    onValueChange = { agreement = agreement.toggle() })
                .padding(start = 4.dp, end = 14.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = agreement.accepted, onCheckedChange = null,
                modifier = Modifier.size(48.dp),
                colors = CheckboxDefaults.colors(checkedColor = c.primary, checkmarkColor = c.onPrimary,
                    uncheckedColor = c.muted))
            Text("Tôi đồng ý để VeriClue xử lý các thông tin trên nhằm xác minh danh tính.",
                style = VcType.body, color = c.ink)
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
