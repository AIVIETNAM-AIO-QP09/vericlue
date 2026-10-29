package vn.vericlue.app.ui.screens

import androidx.compose.foundation.background
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
            if (timedOut) PrimaryButton("Chụp thủ công", onManual, enabled = !taking)
            LinkButton("Dừng quét", onStop)
        }) {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text(if (back) "Lật thẻ để đọc mã QR" else "Đưa mặt có chân dung vào khung", style = VcType.titleLarge, color = c.ink)
                Box(Modifier.fillMaxWidth().aspectRatio(1.586f).clip(RoundedCornerShape(12.dp))) {
                    CameraFeed()
                    if (taking) Box(Modifier.fillMaxSize().background(c.background.copy(alpha = 0.65f)), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = c.accent)
                    }
                }
                Text(if (taking) "Đang chụp ảnh rõ nét" else hint ?: idScanHint(quality, back), style = VcType.bodyStrong, color = c.ink)
                ScanCheck("Đã đọc mã QR", CccdQr.parse(quality?.qr) != null)
                if (!back) ScanCheck("Đã thấy ảnh chân dung", quality?.portraitPresent == true)
                Text("Ứng dụng tự chụp và gửi khi đủ điều kiện. Bạn không cần bấm nút chụp.", style = VcType.bodySmall, color = c.muted)
                if (timedOut) Banner("Giữ đủ bốn góc thẻ trong khung, lau ống kính và tránh phản chiếu đèn. Bạn có thể chụp thủ công; ảnh vẫn cần đọc được QR.")
            }
        }
    }
}

@Composable
private fun ScanCheck(text: String, found: Boolean) {
    val c = Vc.colors
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(if (found) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked,
            contentDescription = null, tint = if (found) c.ok else c.muted, modifier = Modifier.size(22.dp))
        Text(if (found) text else text.removePrefix("Đã ").replaceFirstChar { it.uppercase() } + " — đang tìm", style = VcType.bodySmall, color = c.ink)
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
            Text(if (error == null) "Đang đọc thông tin trên thẻ" else "Chưa thể đọc đủ thông tin", style = VcType.titleLarge, color = c.ink)
            Text(error ?: "Ảnh đã được gửi. Vui lòng giữ ứng dụng mở trong giây lát.", style = VcType.body, color = c.muted)
        }
    }
}
