import SwiftUI

struct BankStartScreen: View {
    let onOpenAccount: () -> Void
    let onGallery: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Image(systemName: "building.columns.fill")
                Text("Ngân hàng Mẫu").font(VcType.section)
                Spacer()
                Image(systemName: "bell")
            }
            .foregroundStyle(.white)
            .padding(20)
            .background(VcPalette.bankGreen)

            Spacer()
            VStack(spacing: 18) {
                ZStack {
                    Circle().fill(VcPalette.bankGreen.opacity(0.12)).frame(width: 112, height: 112)
                    Image(systemName: "creditcard.and.123")
                        .font(.system(size: 46, weight: .medium))
                        .foregroundStyle(VcPalette.bankGreen)
                }
                VcTitleBlock(
                    title: "Mở tài khoản trực tuyến",
                    bodyText: "Chỉ cần CCCD gắn chip và khoảng 2 phút.",
                    centered: true
                )
            }
            Spacer()
            VStack(spacing: 10) {
                VcPrimaryButton(title: "Mở tài khoản", action: onOpenAccount)
                #if DEBUG
                VcSecondaryButton(title: "Xem tất cả màn (bản demo giao diện)", action: onGallery)
                    .accessibilityIdentifier("debug-gallery-button")
                #endif
            }
            .padding(20)
        }
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
    }
}

struct BankOpenedScreen: View {
    let onDone: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        VcScreen(centered: true, showsLogo: false) {
            VcStatusBadge(systemImage: "checkmark.circle.fill", tone: .success)
            VcTitleBlock(title: "Mở tài khoản thành công", bodyText: "Tài khoản mẫu đã sẵn sàng.", centered: true)
            VcChecklistCard(
                title: "Số tài khoản",
                rows: [VcChecklistRow(systemImage: "creditcard", label: "0123 4567 8901", trailing: "Dữ liệu mẫu")]
            )
            VcPrimaryButton(title: "Vào ứng dụng", action: onDone)
        }
        .toolbar(.hidden, for: .navigationBar)
    }
}

struct SplashScreen: View {
    let onDone: () -> Void
    var autoAdvance = true
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 72, weight: .semibold))
                .foregroundStyle(colors.accent)
            VcLogo().scaleEffect(1.45)
            Text("Xác minh danh tính an toàn, nhanh chóng")
                .font(VcType.body)
                .foregroundStyle(colors.muted)
                .multilineTextAlignment(.center)
            Spacer()
            ProgressView()
            Text("Đang khởi động…").font(VcType.caption).foregroundStyle(colors.muted)
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task {
            guard autoAdvance else { return }
            try? await Task.sleep(nanoseconds: 850_000_000)
            guard !Task.isCancelled else { return }
            onDone()
        }
    }
}

struct AuthScreen: View {
    let onRegister: () -> Void
    let onLogin: () -> Void
    let onRecover: () -> Void

    var body: some View {
        VcScreen {
            Spacer(minLength: 24)
            VcTitleBlock(
                title: "Chào mừng bạn đến với VeriClue",
                bodyText: "Xác minh danh tính bằng CCCD, khuôn mặt và giọng nói. Chỉ mất khoảng 2 phút.",
                centered: true
            )
            HStack(spacing: 8) {
                ForEach([("person.text.rectangle", "CCCD"), ("face.smiling", "Khuôn mặt"), ("waveform", "Giọng nói")], id: \.1) { item in
                    VStack(spacing: 8) {
                        Image(systemName: item.0).font(.title2)
                        Text(item.1).font(VcType.labelExtraSmall)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            VcPrimaryButton(title: "Đăng ký", action: onRegister)
            VcSecondaryButton(title: "Đăng nhập", action: onLogin)
            Button(action: onRecover) {
                (Text("Mất tài khoản? ").foregroundColor(.secondary) + Text("Khôi phục tài khoản"))
                    .font(VcType.label)
            }
            .frame(maxWidth: .infinity)
            VcBanner(
                text: "Dữ liệu được mã hóa khi truyền và chỉ dùng để xác minh. Khi tiếp tục, bạn đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư.",
                systemImage: "lock.shield"
            )
        }
    }
}

private let termsSections: [(String, String)] = [
    ("1. Mục đích xử lý dữ liệu", "VeriClue xác minh danh tính của bạn khi mở tài khoản, đăng nhập trên thiết bị mới hoặc khôi phục tài khoản. Ứng dụng chụp ảnh và quay video ngắn khuôn mặt, đổi màu màn hình trong vài giây để kiểm tra camera, và có thể yêu cầu bạn đọc một câu."),
    ("2. Dữ liệu được thu thập", "• Ảnh hai mặt CCCD và thông tin đọc từ mã QR trên thẻ.\n• Ảnh và video ngắn khuôn mặt.\n• Bản ghi giọng đọc một câu ngắn.\n• Số điện thoại để nhận mã xác nhận."),
    ("3. Thời gian lưu", "Dữ liệu khuôn mặt và giọng nói tự xóa sau 24 giờ nếu xác minh thành công, hoặc sau 30 ngày nếu hồ sơ cần nhân viên xem xét. [chờ nhóm chốt]"),
    ("4. Ai được xem dữ liệu", "Chỉ nhân viên thẩm định được giao hồ sơ của bạn. Mọi lần xem đều được ghi nhật ký."),
    ("5. Không dùng để huấn luyện AI", "Dữ liệu của bạn không được dùng để huấn luyện mô hình AI."),
    ("6. Quyền của bạn", "Bạn có thể dừng xác minh bất cứ lúc nào. Bạn có quyền xem, rút lại sự đồng ý và yêu cầu xóa dữ liệu theo quy định pháp luật Việt Nam về bảo vệ dữ liệu cá nhân. Cách gửi yêu cầu: [chờ nhóm chốt]."),
    ("7. Bên kiểm soát dữ liệu", "[Tên, địa chỉ và kênh liên hệ của bên kiểm soát dữ liệu – chờ nhóm chốt]."),
    ("8. Thay đổi điều khoản", "Khi điều khoản thay đổi, ứng dụng sẽ thông báo và hỏi lại sự đồng ý của bạn trước khi tiếp tục xử lý dữ liệu.")
]

struct TermsScreen: View {
    let onAccept: () -> Void
    @State private var reachedEnd = false
    @State private var accepted = false
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(spacing: 0) {
            VcStepProgress(step: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VcTitleBlock(title: "Điều khoản sử dụng", bodyText: "Đọc hết nội dung bên dưới để đồng ý và tiếp tục.")
                    VcBanner(text: "Nội dung mẫu · chờ nhóm và pháp chế chốt", tone: .warning)
                    ForEach(Array(termsSections.enumerated()), id: \.offset) { _, section in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(section.0).font(VcType.section).foregroundStyle(colors.ink)
                            Text(section.1).font(VcType.bodySmall).foregroundStyle(colors.muted)
                        }
                    }
                    Text("Phiên bản demo · cập nhật 22/10/2026")
                        .font(VcType.footnote).foregroundStyle(colors.muted)
                    Button("Bạn đã đọc đến cuối điều khoản") { reachedEnd = true }
                        .font(VcType.label)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
                    Toggle(
                        "Tôi đã đọc hết và đồng ý với Điều khoản sử dụng và Chính sách xử lý dữ liệu cá nhân.",
                        isOn: Binding(get: { accepted }, set: { accepted = reachedEnd ? $0 : false })
                    )
                    .font(VcType.bodySmall)
                    Text(accepted ? "Đã đồng ý." : reachedEnd ? "Bạn đã đọc hết. Tích để đồng ý." : "Kéo xuống cuối điều khoản để bật ô này.")
                        .font(VcType.caption)
                        .foregroundStyle(colors.muted)
                }
                .padding(20)
            }
        }
        .background(colors.background.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            VcPrimaryButton(title: "Đồng ý và tiếp tục", action: onAccept, enabled: accepted)
                .padding(20).background(colors.background)
        }
        .navigationTitle("Điều khoản")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct ConsentChoice: Identifiable {
    let id: Int
    let title: String
    let detail: String
    let required: Bool
}

struct ConsentScreen: View {
    let onContinue: () -> Void
    @State private var selected: Set<Int> = [0, 2]
    @Environment(\.vcColors) private var colors

    private let choices = [
        ConsentChoice(id: 0, title: "Xử lý khuôn mặt và giọng nói", detail: "Để xác minh bạn là người thật và đúng chủ CCCD. Tự xóa sau 24 giờ nếu thành công, hoặc sau 30 ngày nếu cần xem xét.", required: true),
        ConsentChoice(id: 1, title: "Lưu mẫu khuôn mặt đã mã hóa", detail: "Để lần sau xác thực nhanh hơn.", required: false),
        ConsentChoice(id: 2, title: "Lưu thông tin CCCD", detail: "Để mở và quản lý tài khoản.", required: true)
    ]

    private var canContinue: Bool { selected.contains(0) && selected.contains(2) }

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Đồng ý xử lý dữ liệu", bodyText: "Bạn chọn từng mục. Dữ liệu của bạn không được dùng để huấn luyện AI.")
            Text("\(selected.count)/\(choices.count) mục đã chọn")
                .font(VcType.label).foregroundStyle(colors.muted)
            ForEach(choices) { choice in
                Button {
                    if selected.contains(choice.id) { selected.remove(choice.id) }
                    else { selected.insert(choice.id) }
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: selected.contains(choice.id) ? "checkmark.square.fill" : "square")
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Text(choice.title).font(VcType.bodyStrong)
                                Spacer()
                                Text(choice.required ? "Bắt buộc" : "Tùy chọn").font(VcType.footnote)
                            }
                            Text(choice.detail).font(VcType.caption).foregroundStyle(colors.muted)
                        }
                    }
                    .foregroundStyle(colors.ink)
                    .padding(16)
                    .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
            VcBanner(text: "Bạn luôn có quyền thay đổi\nRút lại đồng ý hoặc xin xóa dữ liệu bất cứ lúc nào trong Cài đặt › Quyền riêng tư.", systemImage: "hand.raised")
        }
        .safeAreaInset(edge: .bottom) {
            VcPrimaryButton(title: "Đồng ý và tiếp tục", action: onContinue, enabled: canContinue)
                .padding(20).background(colors.background)
        }
    }
}
