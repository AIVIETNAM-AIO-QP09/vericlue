package vn.vericlue.app.ui.screens

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import vn.vericlue.app.ui.components.*
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

@Composable
fun PrivacyStopScreen(busy: Boolean, requested: Boolean, error: Boolean, onResume: () -> Unit, onWithdraw: () -> Unit, onLeaveUnconfirmed: () -> Unit) {
    VcScreen(onBack = if (requested) null else onResume, actions = {
        PrimaryButton(if (busy) "Đang gửi yêu cầu…" else if (error) "Gửi lại yêu cầu" else "Dừng và rút đồng ý", onWithdraw, enabled = !busy)
        if (!requested) SecondaryButton("Tiếp tục xác minh", onResume)
        if (error && !busy) SecondaryButton("Về màn hình chính · chưa xác nhận xóa", onLeaveUnconfirmed)
    }) {
        TitleBlock("Dừng xử lý phiên này?")
        Text("Ứng dụng sẽ dừng camera, micro và yêu cầu server rút đồng ý xử lý phiên. Thao tác này không xóa tài khoản, bản sao lưu hoặc thu hồi chứng nhận đã cấp.", style = VcType.body, color = Vc.colors.ink)
        if (error) Text("Chưa xác nhận được yêu cầu. Hãy kiểm tra kết nối rồi gửi lại. Ứng dụng chưa xác nhận dữ liệu đã được xóa.", style = VcType.body, color = Vc.colors.ink)
    }
}
