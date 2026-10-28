import Foundation

// Android f034fa9 StartScreens.kt; demo copy, NOT approved legal/privacy content.
enum ConsentPolicy {
    struct Choice: Identifiable {
        let id: Int
        let title: String
        let detail: String
        let required: Bool
    }
    static let choices = [
        Choice(id: 0, title: "Xử lý khuôn mặt và giọng nói",
            detail: "Để xác minh bạn là người thật và đúng chủ CCCD. Giọng nói chỉ được ghi khi cần đọc câu. Tự xóa sau 24 giờ nếu thành công, hoặc sau 30 ngày nếu cần xem xét.", required: true),
        Choice(id: 1, title: "Lưu mẫu khuôn mặt đã mã hóa", detail: "Để lần sau xác thực nhanh hơn.", required: false),
        Choice(id: 2, title: "Lưu thông tin CCCD", detail: "Để mở và quản lý tài khoản.", required: false)
    ]
    static var requiredIDs: Set<Int> { Set(choices.filter(\.required).map(\.id)) }
}
