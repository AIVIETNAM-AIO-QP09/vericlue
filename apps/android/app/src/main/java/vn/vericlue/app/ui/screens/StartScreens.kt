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
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Mic
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
        TitleBlock("Mở tài khoản trực tuyến", "Chỉ cần CCCD gắn chip và khoảng 2 phút.")
    }
}

@Composable
fun BankOpenedScreen(onDone: () -> Unit) {
    VcScreen(actions = { SampleAccount(); PrimaryButton("Vào ứng dụng", onDone) }) {
        BankHeader()
        Spacer(Modifier.height(56.dp))
        SuccessBadge()
        TitleBlock("Mở tài khoản thành công")
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
            Text("Xác minh danh tính an toàn, nhanh chóng", style = VcType.bodySmall, color = c.ink)
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
        Text(
            buildAnnotatedString {
                append("Mất tài khoản? ")
                withStyle(SpanStyle(color = c.accent, fontWeight = FontWeight.SemiBold)) { append("Khôi phục tài khoản") }
            },
            style = VcType.caption, color = c.ink, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onRecover).padding(vertical = 6.dp),
        )
        Text(
            "Dữ liệu được mã hóa khi truyền và chỉ dùng để xác minh. Khi tiếp tục, bạn đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư.",
            style = VcType.footnote, color = c.muted, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
    }) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            IdentityIllustration(Modifier.height(200.dp), phase)
            TitleBlock(
                "Mở tài khoản\ntrong 2 phút",
                "Xác minh danh tính bằng CCCD, khuôn mặt và giọng nói. Chỉ mất khoảng 2 phút. Cần: CCCD gắn chip, chỗ đủ sáng và yên tĩnh.",
            )
            Column {
                NumberedRow(1, "CCCD")
                NumberedRow(2, "Khuôn mặt")
                NumberedRow(3, "Giọng nói", last = true)
            }
        }
    }
}

// ── Terms: must scroll to the end before ticking ─────────────────────────────

private val termsSections = listOf(
    "1. Mục đích xử lý dữ liệu" to "VeriClue xác minh danh tính của bạn khi mở tài khoản, đăng nhập trên thiết bị mới hoặc khôi phục tài khoản. Ứng dụng chụp ảnh và quay video ngắn khuôn mặt, đổi màu màn hình trong vài giây để kiểm tra camera, và có thể yêu cầu bạn đọc một câu.",
    "2. Dữ liệu được thu thập" to "• Ảnh hai mặt CCCD và thông tin đọc từ mã QR trên thẻ.\n• Ảnh và video ngắn khuôn mặt.\n• Bản ghi giọng đọc một câu ngắn.\n• Số điện thoại để nhận mã xác nhận.",
    "3. Thời gian lưu" to "Dữ liệu khuôn mặt và giọng nói tự xóa sau 24 giờ nếu xác minh thành công, hoặc sau 30 ngày nếu hồ sơ cần nhân viên xem xét. [chờ nhóm chốt]",
    "4. Ai được xem dữ liệu" to "Chỉ nhân viên thẩm định được giao hồ sơ của bạn. Mọi lần xem đều được ghi nhật ký.",
    "5. Không dùng để huấn luyện AI" to "Dữ liệu của bạn không được dùng để huấn luyện mô hình AI.",
    "6. Quyền của bạn" to "Bạn có thể dừng xác minh bất cứ lúc nào. Bạn có quyền xem, rút lại sự đồng ý và yêu cầu xóa dữ liệu theo quy định pháp luật Việt Nam về bảo vệ dữ liệu cá nhân. Cách gửi yêu cầu: [chờ nhóm chốt].",
    "7. Bên kiểm soát dữ liệu" to "[Tên, địa chỉ và kênh liên hệ của bên kiểm soát dữ liệu – chờ nhóm chốt].",
    "8. Thay đổi điều khoản" to "Khi điều khoản thay đổi, ứng dụng sẽ thông báo và hỏi lại sự đồng ý của bạn trước khi tiếp tục xử lý dữ liệu.",
)

/**
 * Terms and per-item consent on one screen (short flow, 24/10): read the terms to the end, tick
 * them, tick each required item. Nothing is pre-ticked: consent has to be the user's own action.
 */
@Composable
fun TermsScreen(onBack: () -> Unit, onAccept: () -> Unit) {
    val c = Vc.colors
    val motion = Vc.motion
    val scroll = rememberScrollState()
    var agreement by remember { mutableStateOf(Agreement()) }
    var checked by remember { mutableStateOf(setOf<Int>()) }
    val required = remember { consentItems.withIndex().filter { it.value.required }.map { it.index }.toSet() }
    val readToEnd = agreement.readToEnd
    val accepted = agreement.accepted
    val atEnd by remember { derivedStateOf { scroll.maxValue > 0 && scroll.value >= scroll.maxValue - 8 } }
    LaunchedEffect(atEnd) {
        if (atEnd) {
            agreement = agreement.reachedEnd()
        }
    }
    val fraction by animateFloatAsState(
        if (readToEnd) 1f else if (scroll.maxValue == 0) 0f else scroll.value.toFloat() / scroll.maxValue,
        animationSpec = motion.tween(),
        label = "read",
    )

    VcScreen(
        onBack = onBack,
        actions = { PrimaryButton("Đồng ý và tiếp tục", onAccept, enabled = agreement.canContinueWith(checked, required)) },
    ) {
        TitleBlock("Điều khoản và đồng ý", "Đọc hết điều khoản, rồi chọn từng mục bên dưới.")
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                LinearProgressIndicator(
                    progress = { fraction },
                    modifier = Modifier.weight(1f).height(4.dp).clip(RoundedCornerShape(2.dp)),
                    color = if (readToEnd) c.ok else c.accent,
                    trackColor = c.border,
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    if (readToEnd) "Đã đọc hết" else "Đang đọc",
                    style = VcType.labelXs,
                    color = if (readToEnd) c.ok else c.muted,
                )
            }
            Box(
                Modifier.fillMaxWidth().height(220.dp),
            ) {
                Column(
                    Modifier.verticalScroll(scroll).padding(vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Text(
                        "Nội dung mẫu · chờ nhóm và pháp chế chốt",
                        style = VcType.labelXs,
                        color = c.warn,
                        modifier = Modifier.clip(RoundedCornerShape(6.dp)).background(c.warnBg).padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                    Text("Phiên bản demo · cập nhật 22/10/2026", style = VcType.footnote, color = c.muted)
                    termsSections.forEach { (h, b) ->
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(h, style = VcType.labelSmall, color = c.ink)
                            Text(b, style = VcType.body, color = c.ink)
                        }
                    }
                    AnimatedVisibility(readToEnd, enter = fadeIn(motion.tween()), exit = fadeOut(motion.tween())) {
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(c.okBg).padding(10.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Icon(Icons.Outlined.CheckCircle, contentDescription = null, tint = c.ok, modifier = Modifier.size(16.dp))
                            Text("Bạn đã đọc đến cuối điều khoản", style = VcType.labelXs, color = c.ok)
                        }
                    }
                }
                androidx.compose.animation.AnimatedVisibility(
                    !readToEnd,
                    enter = fadeIn(motion.tween()),
                    exit = fadeOut(motion.tween()),
                    modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 10.dp),
                ) {
                    Row(
                        Modifier.clip(RoundedCornerShape(50)).background(c.surface).border(1.dp, c.border, RoundedCornerShape(50))
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Kéo xuống để đọc tiếp", style = VcType.labelXs, color = c.accent)
                        Icon(Icons.Outlined.KeyboardArrowDown, contentDescription = null, tint = c.accent, modifier = Modifier.size(16.dp))
                    }
                }
            }
            Row(
                Modifier.fillMaxWidth().clickable(enabled = readToEnd, role = Role.Checkbox) {
                    agreement = agreement.toggle()
                },
                verticalAlignment = Alignment.Top,
            ) {
                Checkbox(
                    checked = accepted,
                    onCheckedChange = { agreement = agreement.toggle() },
                    enabled = readToEnd,
                    colors = CheckboxDefaults.colors(checkedColor = c.primary, checkmarkColor = c.onPrimary, uncheckedColor = c.muted, disabledUncheckedColor = c.muted),
                )
                Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        "Tôi đã đọc hết và đồng ý với Điều khoản sử dụng và Chính sách xử lý dữ liệu cá nhân.",
                        style = VcType.bodySmall,
                        color = if (readToEnd) c.ink else c.muted,
                    )
                    Text(
                        when {
                            accepted -> "Đã đồng ý."
                            readToEnd -> "Bạn đã đọc hết. Tích để đồng ý."
                            else -> "Kéo xuống cuối điều khoản để bật ô này."
                        },
                        style = VcType.footnote,
                        color = if (readToEnd) c.accent else c.muted,
                    )
                }
            }
        }
        ConsentList(checked, onToggle = { i -> checked = if (i in checked) checked - i else checked + i })
    }
}

// ── Per-item consent ──────────────────────────────────────────────────────────

private data class ConsentItem(val icon: ImageVector, val title: String, val detail: String, val required: Boolean)

private val consentItems = listOf(
    ConsentItem(
        Icons.Outlined.Face, "Xử lý khuôn mặt và giọng nói",
        "Để xác minh bạn là người thật và đúng chủ CCCD. Tự xóa sau 24 giờ nếu thành công, hoặc sau 30 ngày nếu cần xem xét.",
        true,
    ),
    ConsentItem(Icons.Outlined.Lock, "Lưu mẫu khuôn mặt đã mã hóa", "Để lần sau xác thực nhanh hơn.", false),
    ConsentItem(Icons.Outlined.Badge, "Lưu thông tin CCCD", "Để mở và quản lý tài khoản.", false),
)

@Composable
private fun ConsentTag(required: Boolean) {
    val c = Vc.colors
    Text(
        if (required) "Bắt buộc" else "Tùy chọn",
        style = VcType.labelXs,
        color = if (required) c.accent else c.muted,
        modifier = Modifier.clip(RoundedCornerShape(6.dp))
            .background(if (required) c.surfaceInfo else c.background)
            .border(1.dp, if (required) c.surfaceInfo else c.border, RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 2.dp),
    )
}

/** The consent items, each ticked on its own (shown under the terms). */
@Composable
private fun ConsentList(checked: Set<Int>, onToggle: (Int) -> Unit) {
    val c = Vc.colors
    val motion = Vc.motion
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Đồng ý xử lý dữ liệu · dữ liệu không dùng để huấn luyện AI", style = VcType.labelSmall, color = c.ink)
        consentItems.forEachIndexed { i, item ->
            val on = i in checked
            val bg by animateColorAsState(if (on) c.surfaceInfo else c.surface, motion.tween(), label = "consent-background")
            val border by animateColorAsState(if (on) c.accent else c.border, motion.tween(), label = "consent-border")
            Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                    .background(bg)
                    .border(if (on) 1.5.dp else 1.dp, border, RoundedCornerShape(14.dp))
                    .clickable(role = Role.Checkbox) { onToggle(i) }
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(item.icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(22.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    ConsentTag(item.required)
                    Text(item.title, style = VcType.labelSmall, color = c.ink)
                    Text(item.detail, style = VcType.body, color = c.ink)
                }
                Checkbox(
                    checked = on,
                    onCheckedChange = { onToggle(i) },
                    colors = CheckboxDefaults.colors(checkedColor = c.primary, checkmarkColor = c.onPrimary, uncheckedColor = c.muted),
                    modifier = Modifier.size(24.dp),
                )
            }
        }
        Text(
            "Bạn có thể rút lại đồng ý hoặc xin xóa dữ liệu bất cứ lúc nào trong Cài đặt › Quyền riêng tư.",
            style = VcType.footnote,
            color = c.muted,
        )
    }
}
