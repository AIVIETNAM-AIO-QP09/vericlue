package vn.vericlue.app.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.WbSunny
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.vericlue.app.flow.OtpRules
import vn.vericlue.app.flow.PhoneRules
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.InfoRow
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.NumericKeypad
import vn.vericlue.app.ui.components.OtpBoxes
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.StepProgress
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.TopBar
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.components.stepLabel
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

@Composable
private fun ShieldTile(icon: androidx.compose.ui.graphics.vector.ImageVector = Icons.Outlined.Shield) {
    val c = Vc.colors
    Box(
        Modifier.size(56.dp).clip(RoundedCornerShape(16.dp)).background(c.surfaceInfo),
        contentAlignment = Alignment.Center,
    ) { Icon(icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(28.dp)) }
}

@Composable
fun IntroScreen(onBack: () -> Unit, onStart: () -> Unit) {
    VcScreen(onBack = onBack, step = 1, actions = { PrimaryButton("Bắt đầu", onStart) }) {
        ShieldTile()
        TitleBlock("Xác minh danh tính", eyebrow = "Xác minh bởi VeriClue")
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(Icons.Outlined.Badge, "Chuẩn bị CCCD gắn chip")
            InfoRow(Icons.Outlined.WbSunny, "Đứng ở nơi đủ sáng")
            InfoRow(Icons.Outlined.Mic, "Nơi yên tĩnh để đọc một câu ngắn")
        }
    }
}

@Composable
fun PermissionScreen(onBack: () -> Unit, onAllow: () -> Unit) {
    VcScreen(onBack = onBack, step = 1, actions = { PrimaryButton("Cho phép và tiếp tục", onAllow) }) {
        ShieldTile()
        TitleBlock(
            "Cho phép dùng camera và micro",
            "Ứng dụng chỉ dùng camera và micro trong lúc xác minh. Bạn có thể đổi quyền trong cài đặt của máy.",
            eyebrow = "Quyền truy cập",
        )
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(Icons.Outlined.CameraAlt, "Camera", "Chụp hai mặt CCCD và kiểm tra khuôn mặt trực tiếp.")
            InfoRow(Icons.Outlined.Mic, "Micro", "Ghi âm câu xác nhận ngắn ở bước giọng nói.")
        }
    }
}

@Composable
fun PhoneScreen(onBack: () -> Unit, onSend: (String) -> Unit) {
    val c = Vc.colors
    var phone by remember { mutableStateOf("") }
    val valid = PhoneRules.isValid(phone)
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = { PrimaryButton("Gửi mã", { onSend(phone) }, enabled = valid) },
        bottom = {
            NumericKeypad(
                onDigit = { phone = PhoneRules.append(phone, it) },
                onBackspace = { phone = phone.dropLast(1) },
                onDone = { if (valid) onSend(phone) },
            )
        },
    ) {
        TitleBlock("Số điện thoại của bạn", "Chúng tôi gửi mã xác nhận gồm 6 số.")
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Số điện thoại", style = VcType.label, color = c.ink)
            Row(
                Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(12.dp)).background(c.surface)
                    .border(if (phone.isNotEmpty()) 2.dp else 1.dp, if (phone.isNotEmpty()) c.accent else c.border, RoundedCornerShape(12.dp))
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Icon(Icons.Outlined.Phone, contentDescription = null, tint = c.muted, modifier = Modifier.size(20.dp))
                Text(
                    if (phone.isEmpty()) "09xx xxx xxx" else PhoneRules.format(phone),
                    style = VcType.body,
                    color = if (phone.isEmpty()) c.muted else c.ink,
                )
            }
            if (valid) Text("✓ Số điện thoại hợp lệ", style = VcType.labelXs, color = c.ok)
        }
    }
}

@Composable
fun OtpScreen(onBack: () -> Unit, onVerified: () -> Unit, startWithError: Boolean = false) {
    val c = Vc.colors
    var code by remember { mutableStateOf(if (startWithError) "472910" else "") }
    var error by remember { mutableStateOf(startWithError) }
    var seconds by remember { mutableIntStateOf(45) }
    LaunchedEffect(Unit) {
        while (seconds > 0) {
            delay(1000)
            seconds--
        }
    }
    fun type(d: Char) {
        if (error) {
            code = ""
            error = false
        }
        code = OtpRules.append(code, d)
    }
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = { PrimaryButton("Xác nhận", onVerified, enabled = OtpRules.isComplete(code) && !error) },
        bottom = { NumericKeypad(onDigit = ::type, onBackspace = { code = code.dropLast(1); error = false }, onDone = { if (OtpRules.isComplete(code) && !error) onVerified() }) },
    ) {
        Banner("SMS mô phỏng · Mã xác nhận VeriClue của bạn là [6 SỐ]. Không chia sẻ mã này.", icon = Icons.Outlined.ChatBubbleOutline)
        Text("Nhập mã xác nhận", style = VcType.titleLarge, color = c.ink)
        OtpBoxes(code, error)
        if (error) Banner("Mã chưa đúng. Bạn còn 2 lần thử.", tone = Tone.Warn)
        Text(
            if (seconds > 0) "Gửi lại mã sau 0:${seconds.toString().padStart(2, '0')}" else "Gửi lại mã",
            style = VcType.caption,
            color = if (seconds > 0) c.muted else c.accent,
            modifier = Modifier.fillMaxWidth().clickable(enabled = seconds == 0, role = Role.Button) { seconds = 45 },
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
    }
}

// ── ID card capture (rear camera, always dark) ───────────────────────────────

@Composable
private fun CardPlaceholder(back: Boolean) {
    Canvas(Modifier.fillMaxSize()) {
        drawRoundRect(Color(0xFFDDEDEA), cornerRadius = androidx.compose.ui.geometry.CornerRadius(16f, 16f))
        val line = Color(0xFF9DB7B2)
        if (!back) {
            drawRoundRect(Color(0xFFB8CCC9), topLeft = Offset(size.width * 0.06f, size.height * 0.3f), size = Size(size.width * 0.24f, size.height * 0.5f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(8f, 8f))
            for (i in 0 until 6) {
                drawRoundRect(line, topLeft = Offset(size.width * 0.36f, size.height * (0.3f + i * 0.09f)), size = Size(size.width * (0.5f - (i % 3) * 0.08f), size.height * 0.035f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f))
            }
            drawRoundRect(Color(0xFFC79A3B), topLeft = Offset(size.width * 0.06f, size.height * 0.1f), size = Size(size.width * 0.12f, size.height * 0.12f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f))
        } else {
            drawRect(Color(0xFF6C807C), topLeft = Offset(size.width * 0.72f, size.height * 0.12f), size = Size(size.width * 0.2f, size.width * 0.2f), style = Stroke(6f))
            for (i in 0 until 3) {
                drawRoundRect(line, topLeft = Offset(size.width * 0.06f, size.height * (0.72f + i * 0.08f)), size = Size(size.width * 0.88f, size.height * 0.035f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f))
            }
        }
    }
}

@Composable
private fun CornerFrame(modifier: Modifier) {
    Canvas(modifier) {
        val l = 22.dp.toPx()
        val w = 3.dp.toPx()
        listOf(Offset(0f, 0f) to Pair(1, 1), Offset(size.width, 0f) to Pair(-1, 1), Offset(0f, size.height) to Pair(1, -1), Offset(size.width, size.height) to Pair(-1, -1))
            .forEach { (o, d) ->
                drawLine(Color.White, o, Offset(o.x + l * d.first, o.y), strokeWidth = w)
                drawLine(Color.White, o, Offset(o.x, o.y + l * d.second), strokeWidth = w)
            }
    }
}

@Composable
fun IdCaptureScreen(back: Boolean, glare: Boolean, onBack: () -> Unit, onCapture: () -> Unit) {
    VcTheme(dark = true) {
        val c = Vc.colors
        SystemBarIcons(c.background)
        Column(Modifier.fillMaxSize().background(c.background).statusBarsPadding()) {
            TopBar(onBack)
            StepProgress(1, stepLabel(1))
            Column(Modifier.weight(1f).padding(horizontal = 20.dp, vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Outlined.CameraAlt, contentDescription = null, tint = c.muted, modifier = Modifier.size(16.dp))
                    Text("Camera sau", style = VcType.footnote, color = c.muted)
                }
                Text(if (back) "Chụp mặt sau CCCD" else "Chụp mặt trước CCCD", style = VcType.titleLarge, color = c.ink)
                Box(Modifier.fillMaxWidth().aspectRatio(1.586f).padding(4.dp)) {
                    Box(Modifier.fillMaxSize().padding(10.dp)) {
                        CardPlaceholder(back)
                        if (glare) {
                            Canvas(Modifier.fillMaxSize()) {
                                drawOval(
                                    androidx.compose.ui.graphics.Brush.radialGradient(
                                        listOf(Color.White.copy(alpha = 0.9f), Color.Transparent),
                                        center = Offset(size.width * 0.62f, size.height * 0.4f),
                                        radius = size.width * 0.28f,
                                    ),
                                    topLeft = Offset(size.width * 0.34f, size.height * 0.05f),
                                    size = Size(size.width * 0.56f, size.height * 0.7f),
                                )
                            }
                        }
                    }
                    CornerFrame(Modifier.fillMaxSize())
                }
                if (glare) {
                    Banner("Ảnh bị lóa, hãy nghiêng thẻ một chút", tone = Tone.Warn, icon = Icons.Outlined.WbSunny)
                } else {
                    Banner("Đặt thẻ gọn trong khung, không bị lóa", tone = Tone.Ok)
                }
                Spacer(Modifier.weight(1f))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterHorizontally)) {
                    listOf(!back, back).forEach { on ->
                        Box(Modifier.size(6.dp).clip(CircleShape).background(if (on) Color.White else c.border))
                    }
                }
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Box(
                        Modifier.size(72.dp).clip(CircleShape).border(4.dp, Color.White, CircleShape).padding(8.dp)
                            .clip(CircleShape).background(Color.White).clickable(role = Role.Button, onClick = onCapture),
                    )
                }
            }
            Spacer(Modifier.navigationBarsPadding())
        }
    }
}

// ── Confirm / edit ID information ─────────────────────────────────────────────

/** Sample data only (shown as such); real values come from the QR code (FLOW-03). */
val sampleIdFields = listOf(
    "Họ và tên" to "NGUYỄN VĂN A",
    "Số CCCD" to "001 095 012 345",
    "Ngày sinh" to "01/01/1995",
    "Giới tính" to "Nam",
    "Nơi thường trú" to "Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
)

@Composable
fun ConfirmInfoScreen(onBack: () -> Unit, onCorrect: () -> Unit, onEdit: () -> Unit) {
    val c = Vc.colors
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = {
            PrimaryButton("Thông tin đúng", onCorrect)
            LinkButton("Sửa thông tin", onEdit)
        },
    ) {
        TitleBlock("Kiểm tra thông tin", "Đọc từ mã QR trên CCCD của bạn.")
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceSubtle)
                .border(1.dp, c.border, RoundedCornerShape(16.dp)).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(
                "Dữ liệu mẫu",
                style = VcType.labelXs,
                color = c.warn,
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).background(c.warnBg).padding(horizontal = 8.dp, vertical = 3.dp),
            )
            sampleIdFields.forEach { (k, v) ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(k, style = VcType.footnote, color = c.muted)
                    Text(v, style = VcType.bodyStrong, color = c.ink)
                }
            }
        }
    }
}

@Composable
fun EditInfoScreen(onBack: () -> Unit, onSave: () -> Unit, onRetake: () -> Unit) {
    val c = Vc.colors
    val values = remember { sampleIdFields.map { mutableStateOf(it.second) } }
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = {
            PrimaryButton("Lưu và tiếp tục", onSave)
            LinkButton("Chụp lại CCCD", onRetake)
        },
    ) {
        TitleBlock("Chỉnh sửa thông tin", "Số CCCD được khóa theo mã QR. Nếu mã QR đọc chưa chuẩn, hãy chụp lại thẻ.")
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            sampleIdFields.forEachIndexed { i, (label, _) ->
                val locked = i == 1
                OutlinedTextField(
                    value = values[i].value,
                    onValueChange = { if (!locked) values[i].value = it },
                    label = { Text(if (locked) "$label · khóa theo mã QR" else label) },
                    readOnly = locked,
                    enabled = !locked,
                    trailingIcon = if (locked) ({ Icon(Icons.Outlined.Lock, contentDescription = "Đã khóa", modifier = Modifier.size(18.dp)) }) else null,
                    singleLine = i != 4,
                    keyboardOptions = KeyboardOptions(keyboardType = if (i == 2) KeyboardType.Number else KeyboardType.Text),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = c.accent,
                        unfocusedBorderColor = c.border,
                        disabledBorderColor = c.border,
                        disabledTextColor = c.ink,
                        disabledContainerColor = c.surfaceSubtle,
                        focusedTextColor = c.ink,
                        unfocusedTextColor = c.ink,
                    ),
                    textStyle = VcType.bodyStrong,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}
