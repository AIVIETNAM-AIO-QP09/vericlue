import SwiftUI

struct IntroScreen: View {
    let onStart: () -> Void

    var body: some View {
        VcScreen(step: 1) {
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 64))
                .foregroundStyle(VcPalette.primary)
                .frame(maxWidth: .infinity)
            VcTitleBlock(title: "Xác minh danh tính", eyebrow: "Xác minh bởi VeriClue")
            VStack(spacing: 10) {
                VcInfoRow(systemImage: "person.text.rectangle", title: "Chuẩn bị CCCD gắn chip")
                VcInfoRow(systemImage: "sun.max", title: "Đứng ở nơi đủ sáng")
                VcInfoRow(systemImage: "mic", title: "Nơi yên tĩnh để đọc một câu ngắn")
            }
        }
        .safeAreaInset(edge: .bottom) { BottomAction { VcPrimaryButton(title: "Bắt đầu", action: onStart) } }
    }
}

struct PermissionScreen: View {
    let onAllow: () -> Void

    var body: some View {
        VcScreen(step: 1) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 60))
                .foregroundStyle(VcPalette.primary)
                .frame(maxWidth: .infinity)
            VcTitleBlock(
                title: "Cho phép dùng camera và micro",
                bodyText: "Ứng dụng chỉ dùng camera và micro trong lúc xác minh. Bạn có thể đổi quyền trong cài đặt của máy.",
                eyebrow: "Quyền truy cập"
            )
            VStack(spacing: 10) {
                VcInfoRow(systemImage: "camera", title: "Camera", detail: "Chụp hai mặt CCCD và kiểm tra khuôn mặt trực tiếp.")
                VcInfoRow(systemImage: "mic", title: "Micro", detail: "Ghi âm câu xác nhận ngắn ở bước giọng nói.")
            }
        }
        .safeAreaInset(edge: .bottom) { BottomAction { VcPrimaryButton(title: "Cho phép và tiếp tục", action: onAllow) } }
    }
}

struct PhoneScreen: View {
    let onSend: (String) -> Void
    @State private var phone = ""
    @Environment(\.vcColors) private var colors

    private var valid: Bool { PhoneRules.isValid(phone) }
    private var formatted: String {
        let groups = [4, 3, 3]
        var result: [String] = []
        var index = phone.startIndex
        for size in groups where index < phone.endIndex {
            let end = phone.index(index, offsetBy: min(size, phone.distance(from: index, to: phone.endIndex)))
            result.append(String(phone[index..<end]))
            index = end
        }
        return result.joined(separator: " ")
    }

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Số điện thoại của bạn", bodyText: "Chúng tôi gửi mã xác nhận gồm 6 số.")
            VStack(alignment: .leading, spacing: 8) {
                Text("Số điện thoại").font(VcType.label).foregroundStyle(colors.ink)
                HStack(spacing: 12) {
                    Image(systemName: "phone").foregroundStyle(colors.muted)
                    Text(phone.isEmpty ? "09xx xxx xxx" : formatted)
                        .font(VcType.body)
                        .foregroundStyle(phone.isEmpty ? colors.muted : colors.ink)
                    Spacer()
                }
                .frame(minHeight: 56)
                .padding(.horizontal, 16)
                .background(colors.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(phone.isEmpty ? colors.border : colors.accent, lineWidth: phone.isEmpty ? 1 : 2))
                if valid { Text("✓ Số điện thoại hợp lệ").font(VcType.labelExtraSmall).foregroundStyle(colors.ok) }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 8) {
                VcPrimaryButton(title: "Gửi mã", action: { onSend(phone) }, enabled: valid).padding(.horizontal, 20)
                VcNumericKeypad(
                    onDigit: { phone = PhoneRules.append(phone, $0) },
                    onBackspace: { if !phone.isEmpty { phone.removeLast() } },
                    onDone: { if valid { onSend(phone) } }
                )
            }
            .padding(.top, 8)
            .background(colors.background)
        }
    }
}

struct OTPDemoScreen: View {
    let startsWithError: Bool
    let onVerified: () -> Void
    @State private var code: String
    @State private var hasError: Bool
    @State private var attemptsLeft: Int
    @State private var resendClock = OTPResendClock()
    @Environment(\.vcColors) private var colors

    init(startsWithError: Bool = false, onVerified: @escaping () -> Void) {
        self.startsWithError = startsWithError
        self.onVerified = onVerified
        _code = State(initialValue: startsWithError ? "472910" : "654321")
        _hasError = State(initialValue: startsWithError)
        _attemptsLeft = State(initialValue: startsWithError ? 4 : 5)
        var clock = OTPResendClock(); clock.sent()
        _resendClock = State(initialValue: clock)
    }

    private var complete: Bool { OtpRules.isComplete(code) && !hasError && attemptsLeft > 0 }

    var body: some View {
        VcScreen(step: 1) {
            VcBanner(text: "Dữ liệu mẫu · SMS mô phỏng: 654321. Không phải mã từ server.", systemImage: "message")
            Text("Nhập mã xác nhận").font(VcType.titleLarge).foregroundStyle(colors.ink)
            VcOTPBoxes(code: code, hasError: hasError)
            if hasError { VcBanner(text: FlowRules.otpWrongText(attemptsLeft), tone: .warning) }
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let seconds = resendClock.remaining(at: context.date)
                let padded = seconds < 10 ? "0\(seconds)" : String(seconds)
                Button(seconds > 0 ? "Gửi lại mã sau 0:\(padded)" : "Gửi lại mã") {
                    guard seconds == 0, attemptsLeft > 0 else { return }
                    code = "654321"; hasError = false; resendClock.sent()
                }
                .disabled(seconds > 0 || attemptsLeft == 0)
                .font(VcType.caption)
                .foregroundStyle(seconds > 0 ? colors.muted : colors.accent)
                .frame(maxWidth: .infinity)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 8) {
                VcPrimaryButton(title: "Xác nhận", action: verify, enabled: complete).padding(.horizontal, 20)
                VcNumericKeypad(onDigit: type, onBackspace: erase, onDone: verify)
                    .disabled(attemptsLeft == 0)
            }
            .padding(.top, 8)
            .background(colors.background)
        }
    }

    private func type(_ digit: Character) {
        if hasError { code = ""; hasError = false }
        code = OtpRules.append(code, digit)
    }

    private func verify() {
        guard complete else { return }
        if code == "654321" { onVerified() }
        else { attemptsLeft -= 1; hasError = true }
    }

    private func erase() {
        if !code.isEmpty { code.removeLast() }
        hasError = false
    }
}

struct IDCaptureScreen: View {
    let isBack: Bool
    var glare = false
    let onCapture: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(spacing: 18) {
            HStack {
                Text("Camera sau").font(VcType.label).foregroundStyle(.white)
                Spacer()
                Image(systemName: "bolt.slash").foregroundStyle(.white)
            }
            VcTitleBlock(
                title: isBack ? "Chụp mặt sau CCCD" : "Chụp mặt trước CCCD",
                bodyText: glare ? "Ảnh bị lóa, hãy nghiêng thẻ một chút" : "Đặt thẻ gọn trong khung, không bị lóa"
            )
            .environment(\.vcColors, .dark)
            VcCameraFrame(cardMode: true, glare: glare)
            Spacer()
            Button(action: onCapture) {
                ZStack {
                    Circle().fill(.white).frame(width: 72, height: 72)
                    Circle().stroke(Color.black.opacity(0.25), lineWidth: 2).frame(width: 60, height: 60)
                }
            }
            .accessibilityLabel("Chụp ảnh")
        }
        .padding(20)
        .background(VcPalette.cameraBackground.ignoresSafeArea())
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

struct IDReviewScreen: View {
    let isBack: Bool
    let onConfirm: () -> Void
    let onRetake: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(
                title: isBack ? "Kiểm tra ảnh mặt sau" : "Kiểm tra ảnh mặt trước",
                bodyText: "Xem lại ảnh trước khi gửi: chữ và ảnh trên thẻ phải rõ, không mờ, không lóa."
            )
            VcCameraFrame(cardMode: true)
                .overlay(alignment: .bottomLeading) {
                    Text("Ảnh thẻ vừa chụp").font(VcType.footnote).padding(10).background(.thinMaterial, in: Capsule()).padding(14)
                }
            VcChecklistCard(
                title: "Kiểm tra chất lượng ảnh",
                rows: [
                    VcChecklistRow(systemImage: nil, label: "Ảnh rõ nét, không mờ", state: .done, trailing: "Ổn"),
                    VcChecklistRow(systemImage: nil, label: "Không bị lóa", state: .done, trailing: "Ổn"),
                    VcChecklistRow(systemImage: nil, label: "Đọc được mã QR", state: isBack ? .done : nil, trailing: isBack ? "Ổn" : nil)
                ]
            )
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: isBack ? "Ảnh rõ, tiếp tục" : "Ảnh rõ, chụp mặt sau", action: onConfirm)
                VcSecondaryButton(title: "Chụp lại", action: onRetake)
            }
        }
    }
}

struct IDField: Identifiable, Hashable {
    let id = UUID()
    let label: String
    var value: String
    var locked = false
}

let sampleIDFields = [
    IDField(label: "Họ và tên", value: "NGUYỄN VĂN A"),
    IDField(label: "Số CCCD", value: "001 095 012 345", locked: true),
    IDField(label: "Ngày sinh", value: "01/01/1995"),
    IDField(label: "Giới tính", value: "Nam"),
    IDField(label: "Nơi thường trú", value: "Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội")
]

struct ConfirmInfoScreen: View {
    let onCorrect: () -> Void
    let onEdit: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Kiểm tra thông tin", bodyText: "Đọc từ mã QR trên CCCD của bạn.")
            VcBanner(text: "Dữ liệu mẫu", systemImage: "info.circle")
            VcChecklistCard(rows: sampleIDFields.map { field in
                VcChecklistRow(systemImage: nil, label: field.label, trailing: field.value)
            })
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Thông tin đúng", action: onCorrect)
                VcSecondaryButton(title: "Sửa thông tin", action: onEdit)
            }
        }
    }
}

struct EditInfoScreen: View {
    let onSave: () -> Void
    let onRetake: () -> Void
    @State private var fields = sampleIDFields
    @Environment(\.vcColors) private var colors

    var body: some View {
        Form {
            Section {
                Text("Số CCCD được khóa theo mã QR. Nếu mã QR đọc chưa chuẩn, hãy chụp lại thẻ.")
                    .font(VcType.bodySmall).foregroundStyle(colors.muted)
            }
            Section {
                ForEach($fields) { $field in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(field.locked ? "\(field.label) · khóa theo mã QR" : field.label).font(VcType.caption)
                        TextField(field.label, text: $field.value)
                            .font(VcType.body)
                            .disabled(field.locked)
                        if field.locked { Text("Đã khóa").font(VcType.footnote).foregroundStyle(colors.muted) }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(colors.background)
        .navigationTitle("Chỉnh sửa thông tin")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Lưu và tiếp tục", action: onSave)
                VcSecondaryButton(title: "Chụp lại CCCD", action: onRetake)
            }
        }
    }
}

struct BottomAction<Content: View>: View {
    @ViewBuilder let content: Content
    @Environment(\.vcColors) private var colors

    init(@ViewBuilder content: () -> Content) { self.content = content() }

    var body: some View {
        VStack(spacing: 8) { content }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 12)
            .background(colors.background)
    }
}
