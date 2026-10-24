package vn.vericlue.app.ui.screens

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.CloudUpload
import androidx.compose.material.icons.outlined.FormatQuote
import androidx.compose.material.icons.outlined.HourglassEmpty
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.MicOff
import androidx.compose.material.icons.outlined.NoPhotography
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.PauseCircle
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Sms
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.StopCircle
import androidx.compose.material.icons.outlined.VideocamOff
import androidx.compose.material.icons.outlined.WbSunny
import androidx.compose.material.icons.outlined.OpenInFull
import androidx.compose.material.icons.outlined.CloseFullscreen
import androidx.compose.material.icons.outlined.CenterFocusWeak
import androidx.compose.material.icons.outlined.PanTool
import androidx.compose.material.icons.outlined.VolumeOff
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material.icons.outlined.Dns
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.ui.components.ChecklistCard
import vn.vericlue.app.ui.components.CameraFeed
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.RowState
import vn.vericlue.app.ui.components.SecondaryButton
import vn.vericlue.app.ui.components.StatusBadge
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

// ── Voice (stage C) ──────────────────────────────────────────────────────────

@Composable
private fun CameraStillOn() {
    val c = Vc.colors
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(width = 52.dp, height = 64.dp).clip(RoundedCornerShape(10.dp))) { CameraFeed() }
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(Modifier.size(6.dp).clip(CircleShape).background(c.ok))
                Text("Camera", style = VcType.labelXs, color = c.ink)
            }
            Text("Camera vẫn bật. Giữ mặt trong khung khi đọc.", style = VcType.caption, color = c.muted)
        }
    }
}

@Composable
private fun Waveform(level: Float? = null) {
    val c = Vc.colors
    val t = rememberInfiniteTransition(label = "wave")
    val p by t.animateFloat(0f, 1f, infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "p")
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.height(28.dp)) {
        val base = listOf(0.3f, 0.7f, 0.45f, 1f, 0.6f, 0.85f, 0.4f, 0.75f, 0.5f, 0.9f, 0.35f)
        base.forEachIndexed { i, b ->
            val amp = level?.let { (0.3f + it * 2f).coerceAtMost(1f) } ?: (if (i % 2 == 0) p else 1f - p)
            val h = (0.25f + b * amp) * 28f
            Box(Modifier.width(3.dp).height(h.dp).clip(RoundedCornerShape(2.dp)).background(c.accent))
        }
    }
}

/**
 * Read-a-sentence screen. [again] is the voice_challenge retry: new sentence, one attempt left.
 * Sentences are examples; the real ones come from the server challenge (LIVE-01).
 */
@Composable
fun VoiceScreen(
    onBack: () -> Unit,
    onFinished: () -> Unit,
    again: Boolean = false,
    startRecording: Boolean = false,
    sentence: String? = null,
    level: Float? = null,
    onStartRecording: () -> Unit = {},
) {
    val c = Vc.colors
    var recording by remember { mutableStateOf(startRecording) }
    VcScreen(onBack = onBack, step = 3) {
        CameraStillOn()
        if (again) {
            TitleBlock("Hãy đọc lại", "Chuyển đến nơi yên tĩnh hơn và đọc to, rõ ràng câu mới bên dưới.")
        } else {
            Text("Đọc to câu sau", style = VcType.titleLarge, color = c.ink)
        }
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceInfo).padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Outlined.FormatQuote, contentDescription = null, tint = c.accent, modifier = Modifier.size(22.dp))
            Text(
                sentence?.let { "“$it”" }
                    ?: if (again) "“Tôi xác nhận mở tài khoản, mã số tám ba năm một.”" else "“Tôi xác nhận mở tài khoản, mã số bốn bảy hai chín.”",
                style = VcType.titleMedium,
                color = c.ink,
            )
        }
        Text(
            if (again) "Số lần đọc lại còn lại: 1" else "Đọc rõ ràng, ở nơi yên tĩnh. Câu thay đổi mỗi lần.",
            style = VcType.caption,
            color = c.muted,
        )
        Spacer(Modifier.height(24.dp))
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.size(76.dp).clip(CircleShape).background(if (recording) Palette.LogoNavy else c.primary)
                    .clickable(role = Role.Button) {
                        if (recording) {
                            onFinished()
                        } else {
                            recording = true
                            onStartRecording()
                        }
                    },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    if (recording) Icons.Outlined.Stop else Icons.Outlined.Mic,
                    contentDescription = if (recording) "Dừng ghi âm" else "Bắt đầu ghi âm",
                    tint = Color.White,
                    modifier = Modifier.size(34.dp),
                )
            }
            if (recording) Waveform(level)
            Text(
                if (recording) "Đang nghe… bấm để dừng" else "Bấm để bắt đầu đọc",
                style = VcType.caption,
                color = c.muted,
            )
        }
    }
}

// ── Checking (stage D) ───────────────────────────────────────────────────────

/** Shows progress per step, never a per-detector verdict (a tick means "processed"). */
@Composable
fun CheckingScreen(purpose: Purpose, onDone: () -> Unit, auto: Boolean = true) {
    val labels = if (purpose == Purpose.Reauth) listOf("Khuôn mặt", "Thiết bị") else listOf("Ảnh giấy tờ", "Khuôn mặt", "Giọng nói")
    var done by remember { mutableIntStateOf(1) }
    LaunchedEffect(auto) {
        if (!auto) return@LaunchedEffect
        while (done < labels.size) {
            delay(1300)
            done++
        }
        delay(900)
        onDone()
    }
    VcScreen(centered = true) {
        StatusBadge(null, spinning = true)
        TitleBlock("Đang kiểm tra", "Thường mất vài giây. Đừng tắt ứng dụng.", centered = true)
        ChecklistCard(
            title = null,
            rows = labels.mapIndexed { i, l ->
                Triple(null, l, if (i < done) RowState.Done else if (i == done) RowState.Doing else RowState.Waiting)
            },
        )
    }
}

// ── Results ──────────────────────────────────────────────────────────────────

@Composable
fun SuccessScreen(purpose: Purpose, onContinue: () -> Unit, auto: Boolean = true, checked: List<String>? = null) {
    LaunchedEffect(auto) {
        if (auto) {
            delay(2600)
            onContinue()
        }
    }
    VcScreen(centered = true) {
        StatusBadge(Icons.Outlined.CheckCircle, Tone.Ok)
        when (purpose) {
            Purpose.Onboarding -> {
                TitleBlock("Xác minh thành công", "Đang quay lại ứng dụng ngân hàng…", centered = true)
                // Live runs pass `checked`: only what the server has really checked.
                val rows = checked ?: listOf("Ảnh giấy tờ", "Khuôn mặt", "Giọng nói")
                ChecklistCard("Đã hoàn tất", rows.map { Triple(null, it, RowState.Done) }, trailing = rows.map { "" })
            }
            Purpose.Reauth -> {
                TitleBlock("Đăng nhập thành công", "Danh tính của bạn đã được xác nhận. Thiết bị này đã được liên kết với tài khoản.", centered = true)
                ChecklistCard("Thiết bị đã liên kết", listOf(Triple(Icons.Outlined.PhoneAndroid, "Điện thoại Android này", null)), trailing = listOf("Vừa xong"))
            }
            Purpose.Recovery -> {
                TitleBlock("Khôi phục thành công", "Danh tính của bạn đã được xác nhận.", centered = true)
                ChecklistCard("Bước tiếp theo", listOf(Triple(Icons.Outlined.PhoneAndroid, "Đặt lại cách đăng nhập", null)), trailing = listOf("[chờ nhóm chốt]"))
            }
        }
    }
}

@Composable
fun ReviewScreen(onBackToBank: () -> Unit) {
    VcScreen(centered = true, actions = { PrimaryButton("Quay lại ứng dụng ngân hàng", onBackToBank) }) {
        StatusBadge(Icons.Outlined.Schedule)
        TitleBlock("Hồ sơ đang được xác minh thêm", "Nhân viên sẽ kiểm tra hồ sơ của bạn. Bạn sẽ nhận tin nhắn khi có kết quả.", centered = true)
        ChecklistCard(
            "Bạn sẽ nhận kết quả qua",
            listOf(Triple(Icons.Outlined.Sms, "Tin nhắn SMS", null), Triple(Icons.Outlined.NotificationsNone, "Thông báo của ứng dụng ngân hàng", null)),
        )
    }
}

/** Quality retry (ADR-0017 §1): specific, with how to fix it, and attempts left. */
@Composable
fun RetryQualityScreen(onBack: () -> Unit, onRetake: () -> Unit, hint: String? = null, attemptsLeft: Int? = 1, hintCode: String? = null) {
    val audio = hintCode == "QUIET_PLACE"
    VcScreen(onBack = onBack, step = 2, centered = true, actions = { PrimaryButton(if (audio) "Thử lại" else "Chụp lại", onRetake) }) {
        StatusBadge(retryHintIcon(hintCode), Tone.Warn)
        TitleBlock(if (audio) "Chưa nghe rõ" else "Ảnh chưa đủ rõ", hint ?: "Hãy ra chỗ sáng hơn và giữ điện thoại ngang tầm mặt.", centered = true)
        if (attemptsLeft != null) Text("Còn $attemptsLeft lần chụp lại", style = VcType.caption, color = Vc.colors.muted)
    }
}

/** Icon matching the server's quality hint (same codes as RetryHint in the contract). */
fun retryHintIcon(code: String?): ImageVector = when (code) {
    "MOVE_CLOSER" -> Icons.Outlined.OpenInFull
    "MOVE_BACK" -> Icons.Outlined.CloseFullscreen
    "FACE_CENTER" -> Icons.Outlined.CenterFocusWeak
    "HOLD_STILL" -> Icons.Outlined.PanTool
    "QUIET_PLACE" -> Icons.Outlined.VolumeOff
    else -> Icons.Outlined.WbSunny
}

/** Challenge retry (ADR-0017 §1): how to do it right, never which check failed. */
@Composable
fun RetryChallengeScreen(onBack: () -> Unit, onRetry: () -> Unit, attemptsLeft: Int? = 1) {
    VcScreen(onBack = onBack, step = 2, centered = true, actions = { PrimaryButton("Thử lại", onRetry) }) {
        StatusBadge(Icons.Outlined.Refresh)
        TitleBlock("Chúng ta thử lại nhé", "Giữ đầu yên, chỉ đưa mắt theo chấm sáng. Khi quay đầu, quay chậm rồi quay lại nhìn thẳng.", centered = true)
        if (attemptsLeft != null) Text("Còn $attemptsLeft lần thử", style = VcType.caption, color = Vc.colors.muted)
    }
}

/** Generic message screen for errors and interruptions. */
@Composable
fun MessageScreen(
    icon: ImageVector,
    title: String,
    body: String,
    primary: Pair<String, () -> Unit>?,
    secondary: Pair<String, () -> Unit>? = null,
    onBack: (() -> Unit)? = null,
    tone: Tone? = null,
) {
    VcScreen(
        onBack = onBack,
        centered = true,
        actions = if (primary == null && secondary == null) null else {
            {
                if (primary != null) PrimaryButton(primary.first, primary.second)
                if (secondary != null) SecondaryButton(secondary.first, secondary.second)
            }
        },
    ) {
        StatusBadge(icon, tone)
        TitleBlock(title, body, centered = true)
    }
}

object Messages {
    @Composable fun CameraDenied(onRetry: () -> Unit, onBack: () -> Unit) = MessageScreen(
        Icons.Outlined.NoPhotography, "Chưa có quyền dùng camera",
        "Hãy cho phép dùng camera trong phần cài đặt của điện thoại rồi thử lại.", "Thử lại" to onRetry, onBack = onBack,
    )

    @Composable fun MicDenied(onRetry: () -> Unit, onBack: () -> Unit) = MessageScreen(
        Icons.Outlined.MicOff, "Chưa có quyền dùng micro",
        "Hãy cho phép dùng micro trong phần cài đặt của điện thoại rồi thử lại.", "Thử lại" to onRetry, onBack = onBack,
    )

    @Composable fun Network(onRetry: () -> Unit, onBack: () -> Unit) = MessageScreen(
        Icons.Outlined.WifiOff, "Không kết nối được",
        "Hãy kiểm tra kết nối mạng rồi thử lại. Các bước bạn đã làm vẫn được giữ.", "Thử lại" to onRetry, onBack = onBack,
    )

    @Composable fun SessionExpired(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Schedule, "Phiên đã hết hạn",
        "Vì an toàn, phiên xác minh chỉ dùng trong một thời gian ngắn. Hãy bắt đầu lại từ ứng dụng ngân hàng.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    /** [redoesFace]: "resume" restarts the face part (stage B/C) instead of going back to the last screen. */
    @Composable fun ExitConfirm(onResume: () -> Unit, onStop: () -> Unit, redoesFace: Boolean = true) = MessageScreen(
        Icons.Outlined.PauseCircle, "Bạn muốn dừng xác minh?",
        if (redoesFace) "Bạn có thể quay lại chuẩn bị hoặc dừng phiên xác minh hiện tại." else "Bạn có thể tiếp tục hoặc dừng phiên xác minh hiện tại.",
        (if (redoesFace) "Quay lại chuẩn bị" else "Tiếp tục") to onResume, "Dừng xác minh" to onStop, onBack = onResume,
    )

    /** "Bỏ qua nháy màu": the face part cannot be done in the app. Promises nothing (nothing was sent). */
    @Composable fun FlashSkipped(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Cần xác minh theo cách khác",
        "Phần khuôn mặt cần màn hình đổi màu nhạt trong vài giây. Nếu bạn không xem được, vui lòng liên hệ ngân hàng để được hướng dẫn cách xác minh khác.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    @Composable fun Stopped(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.StopCircle, "Đã dừng xác minh",
        "Phiên xác minh đã dừng. Khi sẵn sàng, bạn có thể bắt đầu lại từ ứng dụng ngân hàng.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    @Composable fun Uploading(onStop: () -> Unit, onDone: () -> Unit, auto: Boolean = true) {
        LaunchedEffect(auto) {
            if (auto) {
                delay(1500)
                onDone()
            }
        }
        MessageScreen(
            Icons.Outlined.CloudUpload, "Đang gửi dữ liệu",
            "Đang gửi ảnh, video hoặc bản ghi của bước vừa thực hiện. Vui lòng giữ kết nối mạng.",
            null, "Dừng xác minh" to onStop,
        )
    }

    @Composable fun UploadFailed(onResend: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.CloudOff, "Chưa gửi được dữ liệu",
        "Hãy kiểm tra kết nối mạng rồi thử gửi lại. Dữ liệu chưa gửi xong chưa thể được kiểm tra.",
        "Gửi lại" to onResend, "Dừng xác minh" to onStop, onBack = onStop,
    )

    @Composable fun Slow(onWait: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.HourglassEmpty, "Đang mất nhiều thời gian hơn",
        "Hệ thống chưa trả kết quả xác minh. Bạn có thể tiếp tục chờ hoặc dừng phiên.",
        "Tiếp tục chờ" to onWait, "Dừng xác minh" to onStop, onBack = onStop,
    )

    /** FLOW-01 `deny`: a clear failure. Says nothing about why (AGENTS.md §6 rule 3). */
    @Composable fun Denied(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Dns, "Xác thực không thành công",
        "Vui lòng thử lại sau.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    /** FLOW-01 re-auth without a verified device key (SEC-02): the user must recover instead. */
    @Composable fun RecoveryRequired(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Cần xác minh lại đầy đủ",
        "Thiết bị này chưa được liên kết. Hãy làm theo hướng dẫn khôi phục tài khoản trong ứng dụng ngân hàng.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    @Composable fun ServiceDown(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Dns, "Tạm thời chưa thể xác minh",
        "Dịch vụ chưa phản hồi. Vui lòng thử lại sau. Lúc này chưa có kết quả xác minh.",
        "Quay lại ứng dụng ngân hàng" to onBank,
    )

    @Composable fun DeviceNotReady(onCheck: () -> Unit, onBank: () -> Unit, onBack: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Thiết bị chưa đáp ứng",
        "Camera hoặc micro chưa hoạt động ổn định, hoặc thiết bị chưa đáp ứng yêu cầu. Hãy kiểm tra quyền, đóng ứng dụng đang dùng thiết bị rồi thử lại.",
        "Kiểm tra quyền truy cập" to onCheck, "Quay lại ứng dụng ngân hàng" to onBank, onBack = onBack,
    )

    /** ADR-0017 §2: stage B/C interrupted → redo only the face part with a new challenge. */
    @Composable fun Interrupted(onRedo: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.VideocamOff, "Xác minh bị gián đoạn",
        "Camera bị ngắt hoặc ứng dụng đã chuyển sang nền. Thông tin giấy tờ vẫn được giữ; bạn chỉ cần làm lại phần khuôn mặt.",
        "Quay lại chuẩn bị" to onRedo, "Dừng xác minh" to onStop, onBack = onStop,
    )

    @Composable fun NoVoice(onRetry: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.MicOff, "Chưa thu được giọng nói",
        "Bản ghi chưa dùng được hoặc micro đã bị ngắt. Hãy kiểm tra micro và chọn nơi yên tĩnh trước khi chuẩn bị đọc lại.",
        "Chuẩn bị đọc lại" to onRetry, "Dừng xác minh" to onStop, onBack = onRetry,
    )
}
