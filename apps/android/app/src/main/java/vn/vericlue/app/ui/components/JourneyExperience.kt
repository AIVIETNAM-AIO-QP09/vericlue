package vn.vericlue.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

/** Journey position describes navigation, never a verification verdict. */
@Composable
fun JourneyHeader(step: Int) {
    val c = Vc.colors
    Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.clearAndSetSemantics {}) {
            (1..3).forEach { index ->
                Box(Modifier.size(if (index == step) 32.dp else 24.dp)
                    .background(if (index == step) c.primary else c.surfaceSubtle, CircleShape),
                    contentAlignment = Alignment.Center) {
                    Text(index.toString(), style = VcType.footnote,
                        color = if (index == step) c.onPrimary else c.muted)
                }
            }
        }
        Column(Modifier.weight(1f)) {
            Text("BƯỚC $step", style = VcType.labelXs, color = c.muted)
            Text(stepLabel(step), style = VcType.label, color = c.ink)
        }
    }
}

@Composable
fun WelcomePanel() {
    VcTheme(dark = true) {
        Surface(color = Palette.LogoNavy, shape = RoundedCornerShape(28.dp)) {
            Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("ĐỊNH DANH ĐIỆN TỬ", style = VcType.labelXs, color = Vc.colors.accent)
                if (LocalDensity.current.fontScale < 1.5f) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Xác minh\ndanh tính", style = VcType.titleLarge,
                            color = Vc.colors.ink, modifier = Modifier.weight(0.6f).semantics { heading() })
                        IdentityScene3D(Modifier.weight(0.4f).height(136.dp))
                    }
                } else {
                    Text("Xác minh danh tính", style = VcType.titleLarge,
                        color = Vc.colors.ink, modifier = Modifier.semantics { heading() })
                    IdentityScene3D(Modifier.fillMaxWidth().height(112.dp))
                }
                Text("Chuẩn bị thẻ căn cước và chọn nơi đủ sáng.", style = VcType.bodySmall, color = Vc.colors.muted)
            }
        }
    }
}

@Composable
fun JourneyOverview(currentStep: Int? = null) {
    val titles = listOf("Thông tin của bạn", "Xác minh khuôn mặt", "Bổ sung khi cần")
    val details = listOf("Xác nhận số điện thoại và kiểm tra thẻ căn cước.",
        "Làm theo hướng dẫn trên màn hình.", "Chỉ đọc câu xác nhận khi được yêu cầu.")
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        titles.forEachIndexed { index, title ->
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Box(Modifier.size(32.dp).background(
                    if (currentStep == index + 1) Vc.colors.primary else Vc.colors.surfaceSubtle, CircleShape),
                    contentAlignment = Alignment.Center) {
                    Text("${index + 1}", style = VcType.labelSmall,
                        color = if (currentStep == index + 1) Vc.colors.onPrimary else Vc.colors.accent)
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(title, style = VcType.bodyStrong, color = Vc.colors.ink)
                    Text(details[index], style = VcType.bodySmall, color = Vc.colors.muted)
                    if (currentStep == index + 1) Text("Bạn đang ở bước này", style = VcType.caption, color = Vc.colors.accent)
                }
            }
        }
    }
}

enum class HelpTopic { Journey, Phone, Otp }

/** Local, on-demand help. Opening or dismissing it never advances a verification step. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpButton(topic: HelpTopic = HelpTopic.Journey, step: Int? = null, enabled: Boolean = true) {
    var open by rememberSaveable { mutableStateOf(false) }
    TextButton(onClick = { open = true }, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) {
        Icon(Icons.AutoMirrored.Outlined.HelpOutline, contentDescription = null, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(8.dp))
        Text(if (topic == HelpTopic.Journey) "Các bước & trợ giúp" else "Cần trợ giúp?", style = VcType.labelSmall)
    }
    if (open) {
        ModalBottomSheet(onDismissRequest = { open = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Vc.colors.background) {
            HelpSheetContent(topic, step, onClose = { open = false })
        }
    }
}

/** Separate content allows native snapshots at large text without a second window. */
@Composable
fun HelpSheetContent(topic: HelpTopic, step: Int? = null, onClose: () -> Unit) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp)) {
        TitleBlock(when (topic) {
            HelpTopic.Journey -> "Từng bước, rõ ràng"
            HelpTopic.Phone -> "Số điện thoại của bạn"
            HelpTopic.Otp -> "Trợ giúp mã xác nhận"
        }, titleStyle = VcType.titleMedium)
        if (topic == HelpTopic.Journey) JourneyOverview(step)
        val questions = when (topic) {
            HelpTopic.Journey -> listOf(
                "Tôi cần chuẩn bị gì?" to "Thẻ căn cước, điện thoại có camera và kết nối mạng. Chọn nơi đủ sáng, tránh ánh sáng chiếu thẳng từ phía sau.",
                "Tôi có bắt buộc đọc câu xác nhận?" to "Chỉ khi ứng dụng yêu cầu xác minh bổ sung. Bạn không cần đọc trước.",
                "Tôi có thể dừng không?" to "Bạn có thể dừng phiên xác minh. Khi quay lại, ứng dụng sẽ hướng dẫn phần cần thực hiện tiếp hoặc làm lại.")
            HelpTopic.Phone -> listOf(
                "Nhập số như thế nào?" to "Nhập 10 chữ số, bắt đầu bằng 0. Bạn có thể dán số đã sao chép rồi kiểm tra lại trước khi gửi mã.",
                "Tại sao cần số điện thoại?" to "Ứng dụng gửi mã xác nhận để kiểm tra bạn có thể nhận tin nhắn tại số này.")
            HelpTopic.Otp -> listOf(
                "Tôi chưa nhận được mã" to "Kiểm tra tin nhắn và kết nối di động. Khi hết thời gian chờ, chọn Gửi lại mã. Nếu số điện thoại chưa đúng, quay lại bước nhập số.",
                "Tôi đã sao chép mã" to "Chọn Dán mã để điền 6 chữ số, kiểm tra rồi bấm Xác nhận. Không chia sẻ mã với người khác.",
                "Mã không được chấp nhận" to "Kiểm tra và dùng mã mới nhất. Số lần thử còn lại được hiển thị theo phản hồi của hệ thống.")
        }
        questions.forEachIndexed { index, (title, body) ->
            ExpandableAnswer(title, body, initiallyOpen = index == 0)
        }
        PrimaryButton("Đã hiểu", onClose)
    }
}

@Composable
private fun ExpandableAnswer(title: String, body: String, initiallyOpen: Boolean) {
    var expanded by rememberSaveable(title) { mutableStateOf(initiallyOpen) }
    val motion = Vc.motion
    Column {
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth()
            .heightIn(min = 48.dp).semantics { stateDescription = if (expanded) "Đang mở" else "Đang thu gọn" }) {
            Text(title, style = VcType.bodyStrong, color = Vc.colors.ink, modifier = Modifier.weight(1f))
            Icon(if (expanded) Icons.Outlined.KeyboardArrowUp else Icons.Outlined.KeyboardArrowDown, null)
        }
        AnimatedVisibility(expanded, enter = expandVertically(motion.tween(180)), exit = shrinkVertically(motion.tween(180))) {
            Text(body, style = VcType.bodySmall, color = Vc.colors.muted,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp))
        }
        HorizontalDivider(color = Vc.colors.border)
    }
}

@Composable
fun ProcessingPanel(title: String, detail: String) {
    ContentCard {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (Vc.motion.enabled) CircularProgressIndicator(Modifier.size(24.dp).clearAndSetSemantics {},
                color = Vc.colors.accent, strokeWidth = 2.dp)
            else Icon(Icons.Outlined.HourglassEmpty, null, tint = Vc.colors.accent)
            Text(title, style = VcType.bodyStrong, color = Vc.colors.ink,
                modifier = Modifier.weight(1f).semantics { liveRegion = LiveRegionMode.Polite })
        }
        Text(detail, style = VcType.bodySmall, color = Vc.colors.muted)
    }
}

@Composable
fun NextStepCard(title: String, detail: String) {
    ContentCard {
        Text(title, style = VcType.label, color = Vc.colors.accent)
        Text(detail, style = VcType.body, color = Vc.colors.ink)
    }
}
