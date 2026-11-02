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
import androidx.compose.material.icons.outlined.Info
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
import vn.vericlue.app.ui.components.Banner
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
import vn.vericlue.app.capture.VoiceCapturePhase
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.ui.components.ChecklistCard
import vn.vericlue.app.ui.components.CompletionHaptic
import vn.vericlue.app.ui.components.SuccessBadge
import vn.vericlue.app.ui.components.IdentityScene3D
import vn.vericlue.app.ui.components.IllustrationScene
import vn.vericlue.app.ui.components.ContentCard
import vn.vericlue.app.ui.components.FeatureRow
import vn.vericlue.app.ui.components.NextStepCard
import vn.vericlue.app.ui.components.ProcessingPanel
import vn.vericlue.app.ui.components.SampleAccount
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
            Text("Giữ khuôn mặt trong khung khi đọc.", style = VcType.caption, color = c.muted)
        }
    }
}

@Composable
private fun Waveform(level: Float? = null) {
    val c = Vc.colors
    val motion = Vc.motion
    val p = if (motion.enabled) {
        val t = rememberInfiniteTransition(label = "wave")
        val value by t.animateFloat(0f, 1f, infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "p")
        value
    } else 0.5f
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
    capturePhase: VoiceCapturePhase = if (startRecording) VoiceCapturePhase.Recording else VoiceCapturePhase.Idle,
) {
    val c = Vc.colors
    val recording = capturePhase == VoiceCapturePhase.Recording
    val preparing = capturePhase == VoiceCapturePhase.Preparing
    val processing = capturePhase == VoiceCapturePhase.Finished
    VcScreen(onBack = onBack, step = 3, actions = {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.size(76.dp).clip(CircleShape).background(if (recording) Palette.LogoNavy else c.primary)
                    .clickable(enabled = capturePhase in setOf(VoiceCapturePhase.Idle, VoiceCapturePhase.Recording), role = Role.Button) {
                        if (recording) {
                            onFinished()
                        } else {
                            onStartRecording()
                        }
                    },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    if (preparing || processing) Icons.Outlined.HourglassEmpty else if (recording) Icons.Outlined.Stop else Icons.Outlined.Mic,
                    contentDescription = if (preparing) "Đang chuẩn bị ghi âm" else if (processing) "Đang xử lý bản ghi" else if (recording) "Dừng ghi âm" else "Bắt đầu ghi âm",
                    tint = if (recording) Color.White else c.onPrimary,
                    modifier = Modifier.size(34.dp),
                )
            }
            if (recording) Waveform(level)
            Text(
                when (capturePhase) {
                    VoiceCapturePhase.Preparing -> "Đang chuẩn bị · Chờ thông báo rồi bắt đầu đọc"
                    VoiceCapturePhase.Recording -> "Đang ghi âm · Đọc câu rồi chạm để kết thúc"
                    VoiceCapturePhase.Finished -> "Đang xử lý bản ghi"
                    VoiceCapturePhase.Failed -> "Chưa thể bắt đầu ghi âm"
                    VoiceCapturePhase.Idle -> "Chạm và chờ sẵn sàng rồi bắt đầu đọc"
                },
                textAlign = TextAlign.Center,
                style = VcType.caption,
                color = c.muted,
            )
        }
    }) {
        CameraStillOn()
        if (again) {
            TitleBlock("Đọc lại câu xác nhận", "Chọn nơi yên tĩnh và đọc rõ câu bên dưới.", titleStyle = VcType.cameraTitle)
        } else {
            Text("Đọc câu xác nhận", style = VcType.cameraTitle, color = c.ink)
        }
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceInfo).padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Outlined.FormatQuote, contentDescription = null, tint = c.accent, modifier = Modifier.size(22.dp))
            Text(
                sentence?.let { "“$it”" }
                    ?: if (again) "“Tôi xác nhận danh tính, mã số tám ba năm một.”" else "“Tôi xác nhận danh tính, mã số bốn bảy hai chín.”",
                style = VcType.titleMedium,
                color = c.ink,
            )
        }
        Text(
            if (again) "Còn 1 lần đọc lại" else "Đọc rõ từng từ tại nơi yên tĩnh.",
            style = VcType.caption,
            color = c.muted,
        )
    }
}

// ── Checking (stage D) ───────────────────────────────────────────────────────

/** Indeterminate feedback; module completion is not invented from a local timer. */
@Composable
fun CheckingScreen(purpose: Purpose, onDone: () -> Unit, auto: Boolean = true) {
    LaunchedEffect(auto) {
        if (auto) { delay(2500); onDone() }
    }
    VcScreen(centered = true) {
        StatusBadge(Icons.Outlined.HourglassEmpty)
        TitleBlock("Đang xác minh", "Bạn đã gửi yêu cầu. Vui lòng chờ phản hồi.", centered = true)
        ProcessingPanel("Đang xử lý yêu cầu", "Giữ ứng dụng mở và duy trì kết nối mạng. Kết quả sẽ xuất hiện khi hệ thống xử lý xong.")
    }
}

// ── Results ──────────────────────────────────────────────────────────────────

@Composable
fun ManualDemoCompleteScreen(onDone: () -> Unit) {
    VcScreen(centered = true, actions = { PrimaryButton("Về màn hình chính", onDone) }) {
        SuccessBadge()
        TitleBlock("Xác minh thành công", "Các bước AI đã thỏa ngưỡng thử nghiệm của bản demo.", centered = true)
        Banner("Demo · Ngưỡng chưa hiệu chỉnh", tone = Tone.Warn)
        Text("Kết quả phục vụ trình diễn, chưa dùng để mở tài khoản hoặc xác minh danh tính thực tế.", style = VcType.body, color = Vc.colors.ink)
    }
}

@Composable
fun SuccessScreen(
    purpose: Purpose,
    onContinue: () -> Unit,
    auto: Boolean = false,
    checked: List<String>? = null,
    accountReady: Boolean? = null,
    manualFullDemo: Boolean = false,
    preview: Boolean = false,
) {
    CompletionHaptic(true)
    LaunchedEffect(auto) { if (auto) { delay(2600); onContinue() } }
    VcScreen(centered = true, actions = { PrimaryButton("Hoàn tất", onContinue) }) {
        ContentCard {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(20.dp)) {
                Text(if (preview) "XEM TRƯỚC" else "ĐÃ HOÀN TẤT", style = VcType.labelSmall, color = Vc.colors.ok)
                IdentityScene3D(Modifier.fillMaxWidth().height(168.dp), IllustrationScene.Success)
                TitleBlock(if (preview) "Xem trước màn thành công" else "Xác minh thành công",
                    if (preview || accountReady == false) null else "Bạn có thể tiếp tục với dịch vụ.", centered = true)
            }
            if (manualFullDemo) Banner("Demo · Ngưỡng chưa hiệu chỉnh", tone = Tone.Warn)
            if (preview) Banner("Xem trước giao diện · Không chạy AI", tone = Tone.Warn)
            if (accountReady == false) Text("Phiên xác minh đã hoàn tất. Tài khoản chưa được lưu trên thiết bị; bạn chưa thể dùng đăng nhập lại.", style = VcType.body, color = Vc.colors.ink)
            if (!checked.isNullOrEmpty()) ChecklistCard("Nội dung đã xác minh", checked.map { Triple(null, it, RowState.Done) })
        }
    }
}

@Composable
fun ReviewScreen(onBackToBank: () -> Unit) {
    VcScreen(centered = true, actions = { PrimaryButton("Về màn hình chính", onBackToBank) }) {
        StatusBadge(Icons.Outlined.Info, tone = Tone.Warn)
        TitleBlock("Chưa hoàn tất xác minh", centered = true)
        NextStepCard("Bạn có thể làm gì?", "Thông tin hiện tại chưa đủ để hoàn tất yêu cầu. Quay về màn hình chính để bắt đầu lại khi sẵn sàng.")
    }
}

@Composable
fun RetryQualityScreen(onBack: () -> Unit, onRetake: () -> Unit, hint: String? = null, attemptsLeft: Int? = 1, hintCode: String? = null, captureIncomplete: Boolean = false) {
    val audio = hintCode == "QUIET_PLACE"
    VcScreen(onBack = onBack, step = if (audio) 3 else 2, centered = true, actions = { PrimaryButton(if (audio || captureIncomplete) "Thử lại" else "Chụp lại", onRetake) }) {
        StatusBadge(if (captureIncomplete) Icons.Outlined.Refresh else retryHintIcon(hintCode), Tone.Warn)
        TitleBlock(if (captureIncomplete) "Thực hiện lại bước khuôn mặt" else if (audio) "Chưa thu rõ giọng nói" else "Chưa thu rõ khuôn mặt", centered = true)
        NextStepCard("Trước khi thử lại", hint ?: if (audio) "Chọn nơi yên tĩnh và đọc rõ từng từ." else "Hãy ra chỗ sáng hơn và giữ điện thoại ngang tầm mặt.")
        if (attemptsLeft != null) Text(if (audio) "Còn $attemptsLeft lần đọc lại" else "Còn $attemptsLeft lần chụp lại", style = VcType.caption, color = Vc.colors.muted)
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
        TitleBlock("Thực hiện lại thử thách", centered = true)
        ContentCard {
            FeatureRow(Icons.Outlined.CenterFocusWeak, "Đưa mắt theo chấm sáng", "Giữ đầu yên, chỉ di chuyển mắt.")
            FeatureRow(Icons.Outlined.Refresh, "Quay đầu chậm", "Làm theo mũi tên rồi quay lại nhìn thẳng.")
        }
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
        TitleBlock(title, centered = true)
        NextStepCard("Hướng dẫn cho bạn", body)
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
        Icons.Outlined.WifiOff, "Chưa thể kết nối",
        "Kiểm tra kết nối mạng rồi thử lại.", "Thử lại" to onRetry, onBack = onBack,
    )

    @Composable fun SessionExpired(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Schedule, "Phiên đã hết hạn",
        "Phiên xác minh đã hết thời gian. Hãy bắt đầu lại.",
        "Về màn hình chính" to onBank,
    )

    /** [redoesFace]: "resume" restarts the face part (stage B/C) instead of going back to the last screen. */
    @Composable fun ExitConfirm(onResume: () -> Unit, onStop: () -> Unit, redoesFace: Boolean = true) = MessageScreen(
        Icons.Outlined.PauseCircle, "Bạn muốn dừng xác minh?",
        if (redoesFace) "Bạn có thể quay lại chuẩn bị hoặc dừng phiên xác minh hiện tại." else "Bạn có thể tiếp tục hoặc dừng phiên xác minh hiện tại.",
        (if (redoesFace) "Quay lại chuẩn bị" else "Tiếp tục") to onResume, "Dừng xác minh" to onStop, onBack = onResume,
    )

    /** "Bỏ qua nháy màu": the face part cannot be done in the app. Promises nothing (nothing was sent). */
    @Composable fun FlashSkipped(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Bạn đã rời bước xác minh",
        "Luồng này chưa hỗ trợ xác minh không đổi màu màn hình. Yêu cầu chưa được hoàn tất.",
        "Về màn hình chính" to onBank,
    )

    @Composable fun Stopped(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.StopCircle, "Đã dừng xác minh",
        "Khi sẵn sàng, bạn có thể bắt đầu một phiên xác minh mới.",
        "Về màn hình chính" to onBank,
    )

    @Composable fun Uploading(onStop: () -> Unit, onDone: () -> Unit, auto: Boolean = true) {
        LaunchedEffect(auto) {
            if (auto) {
                delay(1500)
                onDone()
            }
        }
        VcScreen(centered = true, actions = { SecondaryButton("Dừng xác minh", onStop) }) {
            StatusBadge(Icons.Outlined.CloudUpload)
            TitleBlock("Đang gửi dữ liệu", "Bước vừa thực hiện đang được gửi đi.", centered = true)
            ProcessingPanel("Đang gửi, vui lòng chờ", "Giữ kết nối mạng trong khi ứng dụng gửi ảnh, video hoặc bản ghi. Bạn có thể dừng phiên bằng nút bên dưới.")
        }
    }

    /** The MP4 is still being written on the phone; network errors use ErrorNetwork instead. */
    @Composable fun UploadFailed(onResend: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.CloudOff, "Chưa gửi được dữ liệu",
        "Video chưa sẵn sàng để gửi. Vui lòng thử lại sau một chút.",
        "Thử lại" to onResend, "Dừng xác minh" to onStop, onBack = onStop,
    )

    @Composable fun Slow(onWait: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.HourglassEmpty, "Đang chờ kết quả",
        "Hệ thống chưa trả kết quả xác minh. Bạn có thể tiếp tục chờ hoặc dừng phiên.",
        "Tiếp tục chờ" to onWait, "Dừng xác minh" to onStop, onBack = onStop,
    )

    /** FLOW-01 `deny`: a clear failure. Says nothing about why (AGENTS.md §6 rule 3). */
    @Composable fun Denied(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Dns, "Chưa hoàn tất xác minh",
        "Vui lòng thử lại sau.",
        "Về màn hình chính" to onBank,
    )

    /** FLOW-01 re-auth without a verified device key (SEC-02): the user must recover instead. */
    @Composable fun RecoveryRequired(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Cần xác minh lại đầy đủ",
        "Thiết bị này chưa được liên kết. Hãy làm theo hướng dẫn khôi phục tài khoản trong ứng dụng ngân hàng.",
        "Về màn hình chính" to onBank,
    )

    @Composable fun ServiceDown(onBank: () -> Unit) = MessageScreen(
        Icons.Outlined.Dns, "Tạm thời chưa thể xác minh",
        "Dịch vụ chưa phản hồi. Vui lòng thử lại sau. Lúc này chưa có kết quả xác minh.",
        "Về màn hình chính" to onBank,
    )

    @Composable fun DeviceNotReady(onCheck: () -> Unit, onBank: () -> Unit, onBack: () -> Unit) = MessageScreen(
        Icons.Outlined.PhoneAndroid, "Chưa thể sử dụng camera hoặc micro",
        "Camera hoặc micro chưa hoạt động ổn định, hoặc thiết bị chưa đáp ứng yêu cầu. Hãy kiểm tra quyền, đóng ứng dụng đang dùng thiết bị rồi thử lại.",
        "Kiểm tra quyền truy cập" to onCheck, "Về màn hình chính" to onBank, onBack = onBack,
    )

    /** ADR-0017 §2: stage B/C interrupted → redo only the face part with a new challenge. */
    @Composable fun Interrupted(onRedo: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.VideocamOff, "Xác minh bị gián đoạn",
        "Camera bị ngắt hoặc ứng dụng đã chuyển sang nền. Thông tin giấy tờ vẫn được giữ; bạn chỉ cần làm lại phần khuôn mặt.",
        "Quay lại chuẩn bị" to onRedo, "Dừng xác minh" to onStop, onBack = onStop,
    )

    @Composable fun FaceExpired(onRedo: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.VideocamOff, "Lượt quay đã hết thời gian",
        "Lượt quay khuôn mặt chỉ có hiệu lực trong ít phút. Thông tin giấy tờ vẫn được giữ; bạn chỉ cần quay lại phần khuôn mặt.",
        "Quay lại phần khuôn mặt" to onRedo, "Dừng xác minh" to onStop, onBack = onStop,
    )

    @Composable fun NoVoice(onRetry: () -> Unit, onStop: () -> Unit) = MessageScreen(
        Icons.Outlined.MicOff, "Chưa thu được giọng nói",
        "Bản ghi chưa dùng được hoặc micro đã bị ngắt. Hãy kiểm tra micro và chọn nơi yên tĩnh trước khi chuẩn bị đọc lại.",
        "Chuẩn bị đọc lại" to onRetry, "Dừng xác minh" to onStop, onBack = onRetry,
    )
}
