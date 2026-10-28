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
            VCSuccessEmblem()
            VcTitleBlock(title: "Mở tài khoản thành công", bodyText: "Tài khoản mẫu đã sẵn sàng.", centered: true)
            VCSampleAccount()
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
            VCSuccessEmblem(checked: false)
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
            VCWelcomeIllustration()
            VcTitleBlock(
                title: "Mở tài khoản\ntrong 2 phút",
                bodyText: "Xác minh bằng CCCD và khuôn mặt, chỉ đọc một câu ngắn khi cần."
            )
            VStack(spacing: 0) {
                VCNumberedRow(number: 1, title: "CCCD")
                VCNumberedRow(number: 2, title: "Khuôn mặt")
                VCNumberedRow(number: 3, title: "Đọc một câu", detail: "Chỉ khi cần")
            }
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
            VcPrimaryButton(title: "Đăng ký", action: onRegister)
            VcSecondaryButton(title: "Đăng nhập", action: onLogin)
            Button(action: onRecover) {
                (Text("Mất tài khoản? ").foregroundColor(.secondary) + Text("Khôi phục tài khoản"))
                    .font(VcType.label).frame(minHeight: 44)
            }
            .frame(maxWidth: .infinity)
            }
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
    @State private var agreement = Agreement()
    @State private var selected: Set<Int> = []
    @Environment(\.vcColors) private var colors
    private var reachedEnd: Bool { agreement.readToEnd }
    private var accepted: Bool { agreement.accepted }

    var body: some View {
        VStack(spacing: 0) {
            VcStepProgress(step: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VcTitleBlock(title: "Điều khoản và đồng ý", bodyText: "Đọc hết điều khoản, rồi chọn từng mục bên dưới.")
                    VcBanner(text: "Nội dung mẫu · chờ nhóm và pháp chế chốt", tone: .warning)
                    ForEach(Array(termsSections.enumerated()), id: \.offset) { _, section in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(section.0).font(VcType.section).foregroundStyle(colors.ink)
                            Text(section.1).font(VcType.bodySmall).foregroundStyle(colors.muted)
                        }
                    }
                    Text("Phiên bản demo · cập nhật 22/10/2026")
                        .font(VcType.footnote).foregroundStyle(colors.muted)
                    Button("Bạn đã đọc đến cuối điều khoản") { agreement.reachedEnd() }
                        .accessibilityIdentifier("terms-read-end")
                        .font(VcType.label)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
                        .contentShape(Rectangle())
                    Button { agreement.toggle() } label: {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: accepted ? "checkmark.square.fill" : "square")
                                .font(.title3)
                            Text("Tôi đã đọc hết và đồng ý với Điều khoản sử dụng và Chính sách xử lý dữ liệu cá nhân.")
                                .font(VcType.bodySmall)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .foregroundStyle(colors.ink)
                        .padding(16)
                        .frame(minHeight: 44)
                        .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("terms-agreement")
                    .accessibilityValue(accepted ? "Đã đồng ý" : "Chưa đồng ý")
                    .disabled(!reachedEnd)
                    Text(accepted ? "Đã đồng ý." : reachedEnd ? "Bạn đã đọc hết. Tích để đồng ý." : "Kéo xuống cuối điều khoản để bật ô này.")
                        .font(VcType.caption)
                        .foregroundStyle(colors.muted)
                    ConsentSelection(selected: $selected)
                }
                .padding(20)
            }
            .accessibilityIdentifier("terms-scroll")
        }
        .background(colors.background.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            VcPrimaryButton(title: "Đồng ý và tiếp tục", action: {
                guard agreement.canContinue(selected: selected, required: ConsentPolicy.requiredIDs) else { return }
                onAccept()
            }, enabled: agreement.canContinue(selected: selected, required: ConsentPolicy.requiredIDs))
                .accessibilityIdentifier("terms-continue")
                .padding(20).background(colors.background)
        }
        .navigationTitle("Điều khoản")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct ConsentSelection: View {
    @Binding var selected: Set<Int>
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Đồng ý xử lý dữ liệu").font(VcType.section)
            Text("\(selected.count)/\(ConsentPolicy.choices.count) mục đã chọn")
                .font(VcType.label).foregroundStyle(colors.muted)
            ForEach(ConsentPolicy.choices) { choice in
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
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("consent-choice-\(choice.id)")
                .accessibilityValue(selected.contains(choice.id) ? "Đã chọn" : "Chưa chọn")
            }
        }
    }
}
