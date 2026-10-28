import SwiftUI
import UIKit
import QuartzCore

struct IdentityPhoneScreen: View {
    @EnvironmentObject private var identity: IdentityFlow
    @Environment(\.vcColors) private var colors
    let onNext: (Route) -> Void

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Số điện thoại của bạn", bodyText: "Chúng tôi gửi mã xác nhận gồm 6 số.")
            Text("Số điện thoại").font(VcType.label)
            Text(identity.phone.isEmpty ? "09xx xxx xxx" : PhoneRules.format(identity.phone))
                .font(VcType.body)
                .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
                .padding(.horizontal, 16)
                .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
                .accessibilityIdentifier("identity-phone")
            if let error = identity.errorText { VcBanner(text: error, tone: .warning) }
            if identity.busy { ProgressView("Đang gửi mã…").font(VcType.caption) }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 8) {
                VcPrimaryButton(title: "Gửi mã", action: send,
                    enabled: PhoneRules.isValid(identity.phone) && !identity.busy)
                    .padding(.horizontal, 20)
                    .accessibilityIdentifier("identity-send-otp")
                VcNumericKeypad(onDigit: identity.appendPhone, onBackspace: {
                    if !identity.phone.isEmpty { identity.phone.removeLast() }
                }, onDone: send)
                .disabled(identity.busy)
            }
            .background(colors.background)
        }
        .navigationBarBackButtonHidden(identity.busy)
    }

    private func send() {
        Task { if let route = await identity.sendOTP() { onNext(route) } }
    }
}

struct IdentityOTPScreen: View {
    @EnvironmentObject private var identity: IdentityFlow
    @Environment(\.vcColors) private var colors
    let onNext: (Route) -> Void
    var onRestart: (() -> Void)? = nil

    var body: some View {
        VcScreen(step: 1) {
            if identity.otpVerified {
                VcTitleBlock(title: "Số điện thoại đã được xác nhận",
                    bodyText: "Mã đã được sử dụng. Không cần nhập hoặc gửi lại mã; bấm Tiếp tục để quay lại bước kế tiếp.")
            } else {
            if let sms = identity.otpSMS {
                VcBanner(text: "SMS mô phỏng · " + sms, systemImage: "message")
            }
            Text("Nhập mã xác nhận").font(VcType.titleLarge)
            VcOTPBoxes(code: identity.code, hasError: identity.otpHasError)
            if let attempts = identity.attemptsLeft {
                Text("Bạn còn \(attempts) lần thử.").font(VcType.caption).foregroundStyle(colors.muted)
            }
            if let error = identity.errorText { VcBanner(text: error, tone: .warning) }
            if identity.busy { ProgressView("Đang xác nhận…").font(VcType.caption) }
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let seconds = identity.resendClock.remaining(at: context.date)
                Button(seconds == 0 ? "Gửi lại mã" : countdown(seconds)) {
                    Task { if let route = await identity.sendOTP(resend: true) { onNext(route) } }
                }
                .disabled(seconds > 0 || identity.busy || identity.attemptsLeft == 0)
                .font(VcType.caption)
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("identity-resend-otp")
            }
            }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 8) {
                if identity.otpVerified {
                    VcPrimaryButton(title: "Tiếp tục") {
                        if let route = identity.continueAfterVerifiedOTP() { onNext(route) }
                    }.padding(.horizontal, 20)
                } else {
                VcPrimaryButton(title: "Xác nhận", action: verify, enabled: canVerify)
                    .padding(.horizontal, 20)
                    .accessibilityIdentifier("identity-verify-otp")
                VcNumericKeypad(onDigit: identity.appendCode, onBackspace: identity.eraseCode, onDone: verify)
                    .disabled(identity.busy || identity.otpLocked)
                if identity.attemptsLeft == 0 {
                    VcSecondaryButton(title: "Bắt đầu lại từ ngân hàng") { onRestart?() }
                        .disabled(identity.busy)
                        .padding(.horizontal, 20)
                }
                }
            }
            .background(colors.background)
        }
        .navigationBarBackButtonHidden(identity.busy)
    }

    private var canVerify: Bool {
        !identity.otpVerified && OtpRules.isComplete(identity.code) && !identity.busy && !identity.otpHasError && !identity.otpLocked
    }
    private func verify() {
        guard canVerify else { return }
        Task { if let route = await identity.verifyOTP() { onNext(route) } }
    }
    private func countdown(_ seconds: Int) -> String {
        "Gửi lại mã sau 0:" + (seconds < 10 ? "0" : "") + String(seconds)
    }
}

struct IdentityCaptureScreen: View {
    let isBack: Bool
    let onNext: (Route) -> Void
    @EnvironmentObject private var identity: IdentityFlow
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var camera = CameraSession()
    @State private var errorText: String?
    @State private var heldPhoto: IDCardPhoto?
    @State private var holdReady = false
    @State private var holdDeadline = 0.0
    @State private var operation = UUID()
    @State private var pending: Task<Void, Never>?

    var body: some View {
        VStack(spacing: 18) {
            HStack {
                Text("Camera sau").font(VcType.label)
                Spacer()
                Image(systemName: "bolt.slash")
            }
            VcTitleBlock(title: isBack ? "Chụp mặt sau CCCD" : "Chụp mặt trước CCCD",
                         bodyText: "Đặt thẻ gọn trong khung, không bị lóa")
            Group {
                if let heldPhoto, let image = UIImage(data: heldPhoto.jpeg) {
                    Image(uiImage: image).resizable().scaledToFit()
                } else { RearCameraPreview(session: camera.session) }
            }
                .aspectRatio(1.586, contentMode: .fit)
                .clipped()
                .overlay(CardCorners().stroke(.white, lineWidth: 3))
                .accessibilityLabel("Khung chụp căn cước")
            if let error = errorText ?? identity.errorText { VcBanner(text: error, tone: .warning) }
            if camera.busy { ProgressView("Đang chuẩn bị ảnh…").tint(.white).font(VcType.caption) }
            if let failure = camera.failure {
                VcBanner(text: cameraErrorText(failure), tone: .warning)
                Button("Mở Cài đặt") { openCameraSettings() }.font(VcType.label)
                Button("Thử lại") { Task { await camera.start(isBack: isBack) } }.font(VcType.label)
            }
            if heldPhoto != nil {
                VcSecondaryButton(title: "Chụp lại mặt này", action: retake)
                VcPrimaryButton(title: "Tiếp tục", action: advance,
                    enabled: holdReady && heldPhoto?.canContinue(isBack: isBack) == true)
            } else {
                Text(autoHint).font(VcType.caption)
            }
            Spacer(minLength: 0)
            Button(action: capture) {
                Circle().fill(.white).frame(width: 72, height: 72)
                    .overlay(Circle().stroke(.black.opacity(0.25), lineWidth: 2).padding(6))
            }
            .disabled(!camera.ready || camera.busy || heldPhoto != nil)
            .opacity(camera.ready && !camera.busy && heldPhoto == nil ? 1 : 0.4)
            .accessibilityLabel("Chụp ảnh")
        }
        .padding(20)
        .foregroundStyle(.white)
        .environment(\.vcColors, .dark)
        .background(VcPalette.cameraBackground.ignoresSafeArea())
        .toolbarColorScheme(.dark, for: .navigationBar)
        .navigationBarBackButtonHidden(camera.busy)
        .task(id: scenePhase) {
            if scenePhase == .active {
                if heldPhoto == nil { await camera.start(isBack: isBack) }
                else {
                    let remaining = max(0, holdDeadline - CACurrentMediaTime())
                    try? await Task.sleep(for: .seconds(remaining))
                    if !Task.isCancelled { holdReady = true } // Resume never auto-advances a paused shot.
                }
            } else { cancelPending(); camera.stop() }
        }
        .onChange(of: camera.shouldAutoCapture) { ready in if ready { capture() } }
        .onDisappear { cancelPending(); camera.stop() }
    }

    private func capture() {
        guard camera.ready, !camera.busy, heldPhoto == nil, pending == nil else { return }
        let id = UUID()
        operation = id
        pending = Task {
            defer { if operation == id { pending = nil } }
            do {
                errorText = nil
                let photo = try await camera.capture()
                guard operation == id, !Task.isCancelled, scenePhase == .active else { return }
                identity.acceptPhoto(photo, isBack: isBack)
                camera.stop()
                heldPhoto = photo; holdReady = false
                holdDeadline = CACurrentMediaTime() + IDAutoCapture.pause
                if !photo.sharp { errorText = "Ảnh bị mờ, hãy chụp lại." }
                else if !photo.noGlare { errorText = "Thẻ bị lóa, hãy nghiêng nhẹ thẻ rồi chụp lại." }
                try await Task.sleep(for: .seconds(IDAutoCapture.pause))
                guard operation == id, !Task.isCancelled, scenePhase == .active else { return }
                holdReady = true
                if photo.canContinue(isBack: isBack) { advance() }
            } catch CameraError.cancelled {
                // Background/navigation cancelled the shot; do not advance.
            } catch {
                guard operation == id, !Task.isCancelled else { return }
                errorText = "Chưa chụp được ảnh. Hãy giữ điện thoại ổn định rồi chụp lại."
            }
        }
    }

    private var autoHint: String {
        guard let sample = camera.observation else { return "Giữ thẻ trong khung. Máy sẽ tự chụp khi sẵn sàng; vẫn có thể bấm chụp tay." }
        if !sample.looksLikeCard { return "Đưa CCCD vào khung để máy nhận ra nội dung thẻ." }
        if !sample.qualityGood { return "Giữ thẻ rõ nét, không bị lóa." }
        return "Giữ yên thẻ để tự chụp."
    }

    private func cancelPending() { operation = UUID(); pending?.cancel(); pending = nil }
    private func retake() {
        cancelPending(); camera.stop(); identity.retake(isBack: isBack)
        heldPhoto = nil; holdReady = false; errorText = nil
        let id = UUID(); operation = id
        pending = Task {
            defer { if operation == id { pending = nil } }
            await camera.start(isBack: isBack)
        }
    }
    private func advance() {
        guard scenePhase == .active, holdReady, heldPhoto?.canContinue(isBack: isBack) == true else { return }
        cancelPending()
        onNext(isBack || identity.backPhoto != nil ? .idReview : .idBack)
    }

    private func cameraErrorText(_ error: CameraError) -> String {
        switch error {
        case .denied: "Hãy cho phép dùng camera trong phần cài đặt của điện thoại rồi thử lại."
        default: "Camera chưa hoạt động ổn định, hoặc thiết bị chưa đáp ứng yêu cầu. Hãy kiểm tra quyền rồi thử lại."
        }
    }
}

private struct CardCorners: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let rect = rect.insetBy(dx: 2, dy: 2)
        let length: CGFloat = 24
        for (x, y, dx, dy) in [(rect.minX, rect.minY, 1.0, 1.0), (rect.maxX, rect.minY, -1.0, 1.0),
                               (rect.minX, rect.maxY, 1.0, -1.0), (rect.maxX, rect.maxY, -1.0, -1.0)] {
            path.move(to: CGPoint(x: x + dx * length, y: y))
            path.addLine(to: CGPoint(x: x, y: y))
            path.addLine(to: CGPoint(x: x, y: y + dy * length))
        }
        return path
    }
}

struct IdentityReviewScreen: View {
    let onNext: (Route) -> Void
    @EnvironmentObject private var identity: IdentityFlow

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Kiểm tra hai mặt CCCD",
                         bodyText: "Xem lại ảnh trước khi gửi: chữ và ảnh trên thẻ phải rõ, không mờ, không lóa.")
            ForEach([false, true], id: \.self) { isBack in
                let photo = isBack ? identity.backPhoto : identity.frontPhoto
                Text(isBack ? "Mặt sau" : "Mặt trước").font(VcType.section)
            if let photo, let image = UIImage(data: photo.jpeg) {
                Image(uiImage: image).resizable().scaledToFit().accessibilityLabel("Ảnh thẻ vừa chụp")
                VcChecklistCard(title: "Kiểm tra chất lượng ảnh", rows: [
                    VcChecklistRow(systemImage: nil, label: "Ảnh rõ nét, không mờ", state: photo.sharp ? .done : .waiting, trailing: photo.sharp ? "Ổn" : "Chụp lại"),
                    VcChecklistRow(systemImage: nil, label: "Không bị lóa", state: photo.noGlare ? .done : .waiting, trailing: photo.noGlare ? "Ổn" : "Chụp lại"),
                    VcChecklistRow(systemImage: nil, label: "Mã QR ở mặt này", state: photo.hasQR ? .done : nil,
                        trailing: photo.hasQR ? "Đã đọc" : "Kiểm tra mặt còn lại")
                ])
                if !photo.sharp { VcBanner(text: "Ảnh bị mờ, hãy giữ máy chắc tay rồi chụp lại.", tone: .warning) }
                if !photo.noGlare { VcBanner(text: "Thẻ bị lóa, hãy nghiêng nhẹ thẻ rồi chụp lại.", tone: .warning) }
            } else { VcBanner(text: "Chưa chụp được ảnh. Hãy chụp lại.", tone: .warning) }
                VcSecondaryButton(title: isBack ? "Chụp lại mặt sau" : "Chụp lại mặt trước") {
                    identity.retake(isBack: isBack); onNext(isBack ? .idBack : .idFront)
                }.disabled(identity.busy)
            }
            if identity.cardQR == nil || identity.cardQRRejected {
                VcBanner(text: "Chưa đọc được mã QR trên thẻ. Chọn chụp lại mặt có mã QR, giữ nguyên mặt còn lại.", tone: .warning)
            }
            if let error = identity.errorText { VcBanner(text: error, tone: .warning) }
            if identity.busy { ProgressView("Đang gửi dữ liệu…").font(VcType.caption) }
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Ảnh rõ, gửi hai mặt", action: confirm,
                    enabled: identity.frontPhoto?.canContinue(isBack: false) == true &&
                        identity.backPhoto?.canContinue(isBack: true) == true && identity.cardQR != nil &&
                        !identity.cardQRRejected && !identity.busy)
            }
        }
        .navigationBarBackButtonHidden(identity.busy)
    }

    private func confirm() {
        Task { if let route = await identity.uploadCard() { onNext(route) } }
    }
}

struct IDPairDemoReviewScreen: View {
    let onContinue: () -> Void
    let onRetake: (Route) -> Void
    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Kiểm tra hai mặt CCCD", bodyText: "Dữ liệu mẫu · không dùng ảnh căn cước thật.")
            ForEach([false, true], id: \.self) { isBack in
                Text(isBack ? "Mặt sau · dữ liệu mẫu" : "Mặt trước · dữ liệu mẫu").font(VcType.label)
                VcCameraFrame(cardMode: true)
                VcSecondaryButton(title: isBack ? "Chụp lại mặt sau" : "Chụp lại mặt trước") {
                    onRetake(isBack ? .idBack : .idFront)
                }
            }
            VcPrimaryButton(title: "Ảnh rõ, tiếp tục", action: onContinue)
        }
    }
}

struct IdentityConfirmScreen: View {
    let onNext: (Route) -> Void
    @EnvironmentObject private var identity: IdentityFlow
    @EnvironmentObject private var captures: CaptureFlows
    @EnvironmentObject private var face: FaceCaptureFlow

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: "Kiểm tra thông tin", bodyText: "Đọc từ mã QR trên CCCD của bạn.")
            if let fields = identity.confirmedFields {
                let values = IdentityFlow.displayValues(fields)
                VcChecklistCard(rows: identityFieldLabels.indices.map { index in
                    VcChecklistRow(systemImage: nil, label: identityFieldLabels[index], trailing: values[index])
                })
            } else { VcBanner(text: "Dịch vụ chưa phản hồi. Vui lòng thử lại sau.", tone: .warning) }
            if let error = identity.errorText { VcBanner(text: error, tone: .warning) }
            if identity.busy { ProgressView("Đang gửi dữ liệu…").font(VcType.caption) }
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Thông tin đúng", action: confirm,
                    enabled: face.hasPendingCapture && identity.confirmedFields != nil && !identity.busy)
                VcSecondaryButton(title: "Sửa thông tin", action: { onNext(.editInfo) })
                    .disabled(identity.busy || identity.confirmedFields == nil)
                VcSecondaryButton(title: "Dừng xác minh") { captures.showExitConfirmation = true }
            }
        }
        .navigationBarBackButtonHidden(identity.busy)
    }
    private func confirm() { Task { if let route = await captures.confirmIdentity(identity) { onNext(route) } } }
}

private let identityFieldLabels = ["Họ và tên", "Số CCCD", "Ngày sinh", "Giới tính", "Nơi thường trú"]

struct IdentityEditScreen: View {
    let onNext: (Route) -> Void
    @EnvironmentObject private var identity: IdentityFlow
    @EnvironmentObject private var captures: CaptureFlows
    @EnvironmentObject private var face: FaceCaptureFlow
    @Environment(\.vcColors) private var colors

    var body: some View {
        Form {
            Section {
                Text("Số CCCD được khóa theo mã QR. Nếu mã QR đọc chưa chuẩn, hãy chụp lại thẻ.")
                    .font(VcType.bodySmall)
            }
            Section {
                ForEach(identity.draftValues.indices, id: \.self) { index in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(identityFieldLabels[index]).font(VcType.caption)
                        if index == 1 {
                            Text(identity.draftValues[index]).font(VcType.body)
                            Text("Đã khóa").font(VcType.footnote).foregroundStyle(colors.muted)
                        } else {
                            TextField(identityFieldLabels[index], text: value(at: index))
                                .font(VcType.body)
                                .keyboardType(index == 2 ? .numbersAndPunctuation : .default)
                                .autocorrectionDisabled()
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            if let error = identity.draftError ?? identity.errorText {
                Section { VcBanner(text: error, tone: .warning) }
            }
            if identity.busy { Section { ProgressView("Đang gửi dữ liệu…").font(VcType.caption) } }
        }
        .disabled(identity.busy)
        .scrollContentBackground(.hidden)
        .background(colors.background)
        .navigationTitle("Chỉnh sửa thông tin")
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Lưu và tiếp tục", action: save,
                    enabled: face.hasPendingCapture && !identity.busy && identity.draftError == nil)
                VcSecondaryButton(title: "Chụp lại CCCD", action: {
                    captures.restartFace(live: identity.liveFlow)
                    identity.retake(isBack: false)
                    onNext(.idFront)
                }).disabled(identity.busy)
                VcSecondaryButton(title: "Dừng xác minh") { captures.showExitConfirmation = true }
            }
        }
        .navigationBarBackButtonHidden(identity.busy)
    }

    private func value(at index: Int) -> Binding<String> {
        Binding(get: { identity.draftValues.indices.contains(index) ? identity.draftValues[index] : "" }, set: {
            if identity.draftValues.indices.contains(index) { identity.draftValues[index] = $0 }
        })
    }
    private func save() { Task { if let route = await captures.confirmIdentity(identity) { onNext(route) } } }
}

func openCameraSettings() {
    guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
    UIApplication.shared.open(url)
}

struct IdentityStageCompleteScreen: View {
    let purpose: Purpose
    let onBank: () -> Void

    var body: some View {
        VcScreen(step: 1) {
            VcTitleBlock(title: purpose == .reauth ? "Đã xác nhận số điện thoại" : "Đã xác nhận thông tin",
                bodyText: "Thông tin đã được gửi. Bạn chưa hoàn tất xác minh danh tính.")
            VcBanner(text: "Bước khuôn mặt chưa sẵn sàng trên bản này. Bạn có thể quay lại ứng dụng ngân hàng.")
            VcPrimaryButton(title: "Quay lại ứng dụng ngân hàng", action: onBank)
        }
        .navigationBarBackButtonHidden(true)
    }
}
