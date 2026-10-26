package vn.vericlue.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Local vector illustration; never used over a camera or a light challenge. */
@Composable
fun IdentityIllustration(modifier: Modifier = Modifier, phase: Float = 0f) {
    val c = Vc.colors
    Canvas(modifier.fillMaxWidth().height(168.dp)) {
        val unit = size.height / 180f
        val center = Offset(size.width / 2f, size.height / 2f)
        drawCircle(c.illustration, 83f * unit, center)
        rotate(8f, center) {
            val top = Offset(center.x - 92f * unit, center.y - 30f * unit + phase * 3f * unit)
            drawRoundRect(Palette.Black.copy(alpha = 0.04f), top + Offset(0f, 7f * unit), Size(145f * unit, 92f * unit), CornerRadius(11f * unit))
            drawRoundRect(Palette.White, top, Size(145f * unit, 92f * unit), CornerRadius(11f * unit))
            drawRoundRect(Palette.CardChip, top + Offset(20f * unit, 20f * unit), Size(19f * unit, 12f * unit), CornerRadius(3f * unit))
            repeat(3) { i ->
                drawLine(Palette.CardLine, top + Offset(20f * unit, (49f + i * 10f) * unit), top + Offset((101f - i * 9f) * unit, (49f + i * 10f) * unit), 3f * unit, StrokeCap.Round)
            }
        }
        val face = Offset(center.x + 56f * unit, center.y + 18f * unit)
        drawCircle(Palette.LogoNavy, 34f * unit, face)
        drawCircle(c.warmAccent, 41f * unit, face, style = Stroke(2f * unit, pathEffect = PathEffect.dashPathEffect(floatArrayOf(7f * unit, 6f * unit))))
    }
}

@Composable
fun NumberedRow(number: Int, text: String, detail: String? = null, last: Boolean = false) {
    val c = Vc.colors
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(28.dp).background(if (last) c.warmAccent else c.primary, CircleShape), contentAlignment = Alignment.Center) {
            Text(number.toString(), style = VcType.labelSmall, color = if (last) c.onWarmAccent else c.onPrimary)
        }
        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(text, style = VcType.bodyStrong, color = c.ink)
            if (detail != null) Text(detail, style = VcType.bodySmall, color = c.ink)
        }
    }
}

@Composable
fun CheckMark(modifier: Modifier = Modifier, color: Color = Vc.colors.ok) {
    Canvas(modifier.size(18.dp)) {
        val path = Path().apply {
            moveTo(size.width * 0.18f, size.height * 0.51f)
            lineTo(size.width * 0.40f, size.height * 0.73f)
            lineTo(size.width * 0.83f, size.height * 0.25f)
        }
        drawPath(path, color, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
    }
}

/** The number is explicitly sample data until a bank integration provides a real account. */
@Composable
fun SampleAccount(verified: List<String> = emptyList()) {
    val c = Vc.colors
    Column(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Số tài khoản", style = VcType.bodySmall, color = c.ink)
            Text("Dữ liệu mẫu", style = VcType.caption, color = c.muted)
        }
        Text("0123 4567 8901", style = VcType.account, color = c.ink)
        if (verified.isNotEmpty()) {
            Text("Đã hoàn tất", style = VcType.labelSmall, color = c.ink)
            // Wrapping is intentional at large system font scales.
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                verified.forEach { text ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        CheckMark()
                        Text(if (text == "Ảnh giấy tờ") "Giấy tờ" else text, style = VcType.labelSmall, color = c.ok)
                    }
                }
            }
        }
    }
}
