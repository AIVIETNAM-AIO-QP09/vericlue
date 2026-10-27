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
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Phone
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.vericlue.app.flow.OtpRules
import vn.vericlue.app.capture.CccdInfo
import vn.vericlue.app.capture.CccdQr
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.ui.components.CameraFeed
import vn.vericlue.app.ui.components.LocalCameraFeed
import androidx.compose.foundation.Image
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import vn.vericlue.app.flow.PhoneRules
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.NumericKeypad
import vn.vericlue.app.ui.components.OtpBoxes
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.SecondaryButton
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
/**
 * Live mode passes [onCode] (the server checks the code), the simulated SMS text in [sms] and the
 * server's answer in [serverError]; the demo checks nothing and calls [onVerified].
 */
fun OtpScreen(
    onBack: () -> Unit,
    onVerified: () -> Unit,
    startWithError: Boolean = false,
    sms: String? = null,
    serverError: String? = null,
    onCode: ((String) -> Unit)? = null,
    onResend: () -> Unit = {},
    autoCode: String? = null,
) {
    val c = Vc.colors
    var code by remember { mutableStateOf(if (startWithError) "472910" else "") }
    var error by remember { mutableStateOf(startWithError) }
    var filled by remember { mutableStateOf(false) }
    LaunchedEffect(serverError) { if (serverError != null) error = true }
    // A code read from the SMS fills the boxes; the keypad stays for typing it by hand.
    LaunchedEffect(autoCode) {
        if (autoCode != null && OtpRules.isComplete(autoCode)) {
            code = autoCode
            error = false
            filled = true
        }
    }
    val submit = { if (onCode != null) onCode(code) else onVerified() }
    var seconds by remember { mutableIntStateOf(45) }
    LaunchedEffect(Unit) {
        while (seconds > 0) {
            delay(1000)
            seconds--
        }
    }
    fun type(d: Char) {
        filled = false
        if (error) {
            code = ""
            error = false
        }
        code = OtpRules.append(code, d)
    }
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = { PrimaryButton("Xác nhận", submit, enabled = OtpRules.isComplete(code) && !error) },
        bottom = { NumericKeypad(onDigit = ::type, onBackspace = { code = code.dropLast(1); error = false }, onDone = { if (OtpRules.isComplete(code) && !error) submit() }) },
    ) {
        Banner("SMS mô phỏng · " + (sms ?: "Mã xác nhận VeriClue của bạn là [6 SỐ]. Không chia sẻ mã này."), icon = Icons.Outlined.ChatBubbleOutline)
        Text("Nhập mã xác nhận", style = VcType.titleLarge, color = c.ink)
        OtpBoxes(code, error)
        if (filled && !error) Text("Đã tự điền mã từ tin nhắn. Bạn có thể sửa bằng bàn phím.", style = VcType.caption, color = c.muted)
        if (error) Banner(serverError ?: "Mã chưa đúng. Bạn còn 2 lần thử.", tone = Tone.Warn)
        Text(
            if (seconds > 0) "Gửi lại mã sau 0:${seconds.toString().padStart(2, '0')}" else "Gửi lại mã",
            style = VcType.caption,
            color = if (seconds > 0) c.muted else c.accent,
            modifier = Modifier.fillMaxWidth().clickable(enabled = seconds == 0, role = Role.Button) {
                seconds = 45
                code = ""
                error = false
                onResend()
            },
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
private fun PhotoOrPlaceholder(photo: ByteArray?, back: Boolean, description: String) {
    val bitmap = remember(photo) {
        photo?.let { android.graphics.BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }
    if (bitmap != null) {
        Image(bitmap, contentDescription = description, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(10.dp)))
    } else {
        CardPlaceholder(back)
    }
}

/**
 * Rear camera for one side of the card. The app takes the photo itself when the card is sharp and
 * glare-free ([vn.vericlue.app.capture.IdAutoCapture]); the shutter stays as a fallback. With
 * [captured] set, the photo stays on screen for one beat with a "retake" button, then the caller
 * moves on to the next side.
 */
@Composable
fun IdCaptureScreen(
    back: Boolean,
    glare: Boolean,
    onBack: () -> Unit,
    onCapture: () -> Unit,
    captured: Boolean = false,
    photo: ByteArray? = null,
    onRetake: () -> Unit = {},
    capturedOk: Boolean = true,
    hint: String? = null,
) {
    VcTheme(dark = true) {
        val c = Vc.colors
        val side = if (back) "mặt sau" else "mặt trước"
        SystemBarIcons(c.background)
        Column(Modifier.fillMaxSize().background(c.background).statusBarsPadding()) {
            TopBar(onBack)
            StepProgress(1, stepLabel(1))
            Column(Modifier.weight(1f).padding(horizontal = 20.dp, vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Outlined.CameraAlt, contentDescription = null, tint = c.muted, modifier = Modifier.size(16.dp))
                    Text("Camera sau", style = VcType.footnote, color = c.muted)
                }
                Text(if (captured) "Đã chụp $side" else "Đặt $side CCCD vào khung", style = VcType.titleLarge, color = c.ink)
                Box(Modifier.fillMaxWidth().aspectRatio(1.586f).padding(4.dp)) {
                    Box(Modifier.fillMaxSize().padding(10.dp).clip(RoundedCornerShape(12.dp))) {
                        when {
                            captured -> PhotoOrPlaceholder(photo, back, "Ảnh thẻ vừa chụp")
                            LocalCameraFeed.current != null -> CameraFeed()
                            else -> CardPlaceholder(back)
                        }
                        if (glare && !captured) {
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
                    if (captured) {
                        Box(Modifier.fillMaxSize().padding(10.dp).border(3.dp, c.ok, RoundedCornerShape(12.dp)))
                        Text(
                            "✓  Đã chụp $side",
                            style = VcType.label,
                            color = Color.White,
                            modifier = Modifier.align(Alignment.Center).clip(RoundedCornerShape(50)).background(c.ok)
                                .padding(horizontal = 14.dp, vertical = 8.dp),
                        )
                    } else {
                        CornerFrame(Modifier.fillMaxSize())
                    }
                }
                when {
                    captured && capturedOk -> Banner(if (back) "Ảnh rõ. Đang mở màn xem lại" else "Ảnh rõ. Tự sang mặt sau", tone = Tone.Ok)
                    captured -> Banner("Ảnh có thể bị mờ hoặc lóa. Bấm \"Chụp lại\" nếu chữ trên thẻ chưa rõ.", tone = Tone.Warn)
                    hint != null -> Banner(hint, tone = Tone.Warn)
                    glare -> Banner("Ảnh bị lóa, hãy nghiêng thẻ một chút", tone = Tone.Warn, icon = Icons.Outlined.WbSunny)
                    else -> Banner("Giữ thẻ gọn trong khung. Ứng dụng tự chụp khi đủ nét", tone = Tone.Ok)
                }
                Spacer(Modifier.weight(1f))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterHorizontally)) {
                    listOf(!back, back).forEach { on ->
                        Box(Modifier.size(6.dp).clip(CircleShape).background(if (on) Color.White else c.border))
                    }
                }
                if (captured) {
                    SecondaryButton("Chụp lại $side", onRetake)
                } else {
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        Box(
                            Modifier.size(72.dp).clip(CircleShape).border(4.dp, Color.White, CircleShape).padding(8.dp)
                                .clip(CircleShape).background(Color.White).clickable(role = Role.Button, onClick = onCapture)
                                .semantics { contentDescription = "Chụp ảnh" },
                        )
                    }
                }
            }
            Spacer(Modifier.navigationBarsPadding())
        }
    }
}

/**
 * One review of both ID photos after the back side. The rows are quality checks only
 * (ADR-0017 §1), never a verdict on the card. Retaking one side keeps the other.
 */
@Composable
fun IdReviewScreen(
    onBack: () -> Unit,
    onRetakeFront: () -> Unit,
    onRetakeBack: () -> Unit,
    onContinue: () -> Unit,
    front: Pair<ByteArray, IdQuality>? = null,
    back: Pair<ByteArray, IdQuality>? = null,
    onDebugQr: (() -> Unit)? = null,
) {
    val c = Vc.colors
    val hint = idRetakeHint(false, front?.second) ?: idRetakeHint(true, back?.second)
    VcScreen(onBack = onBack, step = 1, actions = { PrimaryButton("Tiếp tục", onContinue) }) {
        TitleBlock("Xem lại ảnh CCCD", "Chữ và ảnh chân dung phải rõ, không bị lóa.")
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceSubtle)
                .border(1.dp, c.border, RoundedCornerShape(16.dp)).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            listOf(Triple(false, front, onRetakeFront), Triple(true, back, onRetakeBack)).forEach { (isBack, shot, retake) ->
                val ok = idChecks(isBack, shot?.second).all { it.second }
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        Modifier.fillMaxWidth().aspectRatio(1.586f).clip(RoundedCornerShape(12.dp))
                            .border(2.dp, if (ok) c.ok else c.warn, RoundedCornerShape(12.dp)).padding(4.dp),
                    ) { PhotoOrPlaceholder(shot?.first, isBack, if (isBack) "Ảnh mặt sau" else "Ảnh mặt trước") }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (isBack) "Mặt sau" else "Mặt trước", style = VcType.bodyStrong, color = c.ink, modifier = Modifier.weight(1f))
                        LinkButton("Chụp lại", retake, Modifier.width(110.dp))
                    }
                }
            }
        }
        hint?.let { Banner(it, tone = Tone.Warn) }
        // Debug builds only: the emulator camera cannot show a QR code.
        onDebugQr?.let { LinkButton("Dùng mã QR mẫu (debug)", it) }
    }
}

/** Quality rows for the review screen. Without a real photo (demo) every row passes. */
private fun idChecks(back: Boolean, q: IdQuality?): List<Pair<String, Boolean>> = buildList {
    add("Ảnh rõ nét, không mờ" to (q?.sharp ?: true))
    add("Không bị lóa" to (q?.noGlare ?: true))
    if (back) add("Đọc được mã QR" to (q == null || CccdQr.parse(q.qr) != null))
}

/** One quality hint for the first failed check (ADR-0017 §1: specific, with how to fix it). */
fun idRetakeHint(back: Boolean, q: IdQuality?): String? = when {
    q == null -> null
    !q.sharp -> "Ảnh bị mờ, hãy giữ máy chắc tay rồi chụp lại."
    !q.noGlare -> "Thẻ bị lóa, hãy nghiêng nhẹ thẻ rồi chụp lại."
    back && CccdQr.parse(q.qr) == null -> "Chưa đọc được mã QR, hãy đưa mặt sau thẻ lại gần hơn rồi chụp lại."
    else -> null
}

/** Rows shown on the confirm screen: from the QR code when read, otherwise the sample data. */
fun idFields(info: CccdInfo?): List<Pair<String, String>> = info?.let {
    listOf(
        "Họ và tên" to it.fullName.uppercase(),
        "Số CCCD" to CccdQr.groupId(it.idNumber),
        "Ngày sinh" to it.dateOfBirth,
        "Giới tính" to it.gender,
        "Nơi thường trú" to it.address,
    )
} ?: sampleIdFields

// ── Confirm / edit ID information ─────────────────────────────────────────────

/** Sample data only (shown as such); real values come from the QR code (FLOW-03). */
val sampleIdFields = listOf(
    "Họ và tên" to "NGUYỄN VĂN A",
    "Số CCCD" to "001 095 012 345",
    "Ngày sinh" to "01/01/1995",
    "Giới tính" to "Nam",
    "Nơi thường trú" to "Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
)

/**
 * Shown after the face recording in the short flow ([afterFace]): the step bar stays on the face
 * step, and the video is sent only after this confirm (the server takes no confirm once it has media).
 */
@Composable
fun ConfirmInfoScreen(
    onBack: () -> Unit,
    onCorrect: () -> Unit,
    onEdit: () -> Unit,
    fields: List<Pair<String, String>> = sampleIdFields,
    afterFace: Boolean = false,
) {
    val c = Vc.colors
    VcScreen(
        onBack = onBack,
        step = if (afterFace) 2 else 1,
        actions = {
            PrimaryButton("Thông tin đúng", onCorrect, enabled = FlowRules.validIdentityValues(fields.map { it.second }))
            LinkButton("Sửa thông tin", onEdit)
        },
    ) {
        if (afterFace) Banner("Đã quay xong. Xem lại thông tin, rồi bấm \"Thông tin đúng\" để gửi.", tone = Tone.Ok)
        TitleBlock("Kiểm tra thông tin", "Thông tin đọc từ ảnh hoặc mã QR trên CCCD. Hãy kiểm tra và sửa những mục chưa đúng.")
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceSubtle)
                .border(1.dp, c.border, RoundedCornerShape(16.dp)).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            if (fields === sampleIdFields) {
                Text(
                    "Dữ liệu mẫu",
                    style = VcType.labelXs,
                    color = c.warn,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).background(c.warnBg).padding(horizontal = 8.dp, vertical = 3.dp),
                )
            }
            fields.forEach { (k, v) ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(k, style = VcType.footnote, color = c.muted)
                    Text(v, style = VcType.bodyStrong, color = c.ink)
                }
            }
        }
    }
}

@Composable
fun EditInfoScreen(
    onBack: () -> Unit,
    onSave: (List<String>) -> Unit,
    onRetake: () -> Unit,
    fields: List<Pair<String, String>> = sampleIdFields,
    hint: String? = null,
) {
    val c = Vc.colors
    val values = remember(fields) { fields.map { mutableStateOf(it.second) } }
    VcScreen(
        onBack = onBack,
        step = 1,
        actions = {
            PrimaryButton("Lưu và tiếp tục", { onSave(values.map { it.value.trim() }) }, enabled = FlowRules.validIdentityValues(values.map { it.value.trim() }))
            LinkButton("Chụp lại CCCD", onRetake)
        },
    ) {
        TitleBlock("Chỉnh sửa thông tin", "Điền thông tin đúng như trên CCCD. Nội dung thay đổi sẽ được kiểm tra lại.")
        hint?.let { Banner(it, tone = Tone.Warn) }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            fields.forEachIndexed { i, (label, _) ->
                val locked = false
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
