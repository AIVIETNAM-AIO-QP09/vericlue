package vn.vericlue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.QrCode2
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.foundation.layout.Row
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import vn.vericlue.app.capture.CccdQr
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.capture.idScanHint
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.CameraFeed
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

@Composable
fun IdScanScreen(
    back: Boolean, quality: IdQuality?, onBack: () -> Unit, onStop: () -> Unit,
    onManual: () -> Unit, timedOut: Boolean = false, taking: Boolean = false,
    hint: String? = null,
) {
    VcTheme(dark = true) {
        val c = Vc.colors
        VcScreen(onBack = onBack, step = 1, actions = {
            if (timedOut) PrimaryButton("Chụp ảnh thẻ", onManual, enabled = !taking)
            LinkButton("Dừng xác minh", onStop)
        }) {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text(if (back) "Quét thêm mặt có mã QR" else "Quét thẻ căn cước", style = VcType.titleLarge, color = c.ink)
                Box(Modifier.fillMaxWidth().aspectRatio(1.586f).clip(RoundedCornerShape(12.dp))) {
                    CameraFeed(placeholder = { CardGuide(back) })
                    if (taking) Box(Modifier.fillMaxSize().background(c.background.copy(alpha = 0.65f)), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = c.accent)
                    }
                }
                Text(if (taking) "Đang chụp ảnh" else hint ?: idScanHint(quality, back), style = VcType.bodyStrong, color = c.ink)
                ScanCheck("Đã đọc mã QR", "Đang tìm mã QR", CccdQr.parse(quality?.qr) != null)
                if (!back) ScanCheck("Đã tìm thấy ảnh chân dung", "Đang tìm ảnh chân dung", quality?.portraitPresent == true)
                if (timedOut) Banner("Đặt đủ bốn góc thẻ trong khung và tránh ánh sáng phản chiếu. Bạn có thể chụp ảnh để thử lại.")
            }
        }
    }
}

/** A schematic guide for preview/no camera permission, never a real ID or readable QR. */
@Composable
private fun CardGuide(back: Boolean) {
    val c = Vc.colors
    Box(Modifier.fillMaxSize().background(c.surface).padding(18.dp), contentAlignment = Alignment.Center) {
        Row(Modifier.fillMaxSize().border(1.dp, c.border, RoundedCornerShape(10.dp)).padding(18.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(18.dp)) {
            Icon(if (back) Icons.Outlined.Badge else Icons.Outlined.Person, contentDescription = null,
                modifier = Modifier.size(64.dp), tint = c.muted)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                repeat(3) { Box(Modifier.fillMaxWidth(if (it == 2) 0.65f else 1f).height(6.dp)
                    .background(c.border, RoundedCornerShape(3.dp))) }
            }
            Icon(Icons.Outlined.QrCode2, contentDescription = null, modifier = Modifier.size(34.dp), tint = c.muted)
        }
    }
}

@Composable
private fun ScanCheck(foundText: String, pendingText: String, found: Boolean) {
    val c = Vc.colors
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(if (found) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked,
            contentDescription = null, tint = if (found) c.ok else c.muted, modifier = Modifier.size(22.dp))
        Text(if (found) foundText else pendingText, style = VcType.bodySmall, color = c.ink)
    }
}

@Composable
fun IdProcessingScreen(onStop: () -> Unit, onRetake: () -> Unit, error: String? = null) {
    val c = Vc.colors
    VcScreen(onBack = onStop, step = 1, actions = {
        if (error != null) PrimaryButton("Quét lại thẻ", onRetake)
        LinkButton("Dừng xác minh", onStop)
    }) {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Spacer(Modifier.height(24.dp))
            if (error == null) CircularProgressIndicator(color = c.accent)
            Text(if (error == null) "Đang đọc thông tin thẻ" else "Chưa đọc được thông tin", style = VcType.titleLarge, color = c.ink)
            if (error != null) Text(error, style = VcType.body, color = c.ink)
        }
    }
}
