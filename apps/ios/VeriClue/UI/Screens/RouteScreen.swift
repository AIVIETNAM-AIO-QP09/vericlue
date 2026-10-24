import SwiftUI

struct RouteScreen: View {
    let route: Route
    @EnvironmentObject private var navigation: AppNavigation
    @EnvironmentObject private var flow: DemoFlow

    var body: some View {
        switch route {
        case .bankStart:
            BankStartScreen(onOpenAccount: { navigation.go(.splash) }, onGallery: { navigation.go(.gallery) })
        case .bankOpened:
            BankOpenedScreen(onDone: finishAtBank)
        case .gallery:
            #if DEBUG
            GalleryScreen()
            #else
            EmptyView()
            #endif
        case .splash:
            SplashScreen(onDone: { navigation.replaceTop(with: .auth) }, autoAdvance: !flow.previewMode)
        case .auth:
            AuthScreen(
                onRegister: { flow.purpose = .onboarding; navigation.go(.terms) },
                onLogin: { flow.purpose = .reauth; navigation.go(.phone) },
                onRecover: { flow.purpose = .recovery; navigation.go(.phone) }
            )
        case .terms:
            TermsScreen(onAccept: { navigation.go(.consent) })
        case .consent:
            ConsentScreen(onContinue: { navigation.go(.intro) })
        case .intro:
            IntroScreen(onStart: { navigation.go(.permission) })
        case .permission:
            PermissionScreen(onAllow: { navigation.go(.phone) })
        case .phone:
            PhoneScreen { _ in navigation.go(.otp) }
        case .otp:
            OTPDemoScreen { navigation.go(flow.afterOTP()) }
        case .otpError:
            OTPDemoScreen(startsWithError: true) { navigation.go(flow.afterOTP()) }
        case .idFront:
            IDCaptureScreen(isBack: false, onCapture: { navigation.go(.idFrontReview) })
        case .idFrontGlare:
            IDCaptureScreen(isBack: false, glare: true, onCapture: { navigation.replaceTop(with: .idFront) })
        case .idFrontReview:
            IDReviewScreen(isBack: false, onConfirm: { navigation.go(.idBack) }, onRetake: navigation.back)
        case .idBack:
            IDCaptureScreen(isBack: true, onCapture: { navigation.go(.idBackReview) })
        case .idBackReview:
            IDReviewScreen(isBack: true, onConfirm: { navigation.go(.confirm) }, onRetake: navigation.back)
        case .confirm:
            ConfirmInfoScreen(onCorrect: { navigation.go(.faceReady) }, onEdit: { navigation.go(.editInfo) })
        case .editInfo:
            EditInfoScreen(onSave: { navigation.go(.faceReady) }, onRetake: { navigation.go(.idFront) })
        case .faceReady:
            FaceReadyScreen(onReady: { navigation.go(.framing) }, onSkipFlash: { navigation.go(.flashSkipped) })
        case .framing:
            FramingScreen(onCaptured: { navigation.go(.holdStill) })
        case .holdStill:
            FaceTimelineDemoScreen(onStop: { navigation.go(.exitConfirm) }, onDone: { navigation.go(.turnHead) })
        case .turnHead:
            TurnHeadScreen(onDone: { navigation.go(flow.afterHeadTurn()) })
        case .voice:
            VoiceScreen(onFinished: { navigation.go(.uploading) })
        case .voiceAgain:
            VoiceScreen(again: true) {
                flow.outcome = .pass
                navigation.go(.uploading)
            }
        case .uploading:
            UploadingScreen(
                onStop: { navigation.go(.exitConfirm) },
                onDone: { navigation.replaceTop(with: .checking) },
                autoAdvance: !flow.previewMode
            )
        case .checking:
            CheckingScreen(
                purpose: flow.purpose,
                onDone: { navigation.replaceTop(with: flow.outcome.destination) },
                autoAdvance: !flow.previewMode
            )
        case .success:
            SuccessScreen(purpose: flow.purpose) {
                if flow.purpose == .onboarding { navigation.go(.bankOpened) }
                else { finishAtBank() }
            }
        case .review:
            ReviewScreen(onBank: finishAtBank)
        case .retryQuality:
            RetryQualityScreen { flow.outcome = .pass; navigation.go(.faceReady) }
        case .retryChallenge:
            RetryChallengeScreen { flow.outcome = .pass; navigation.go(.faceReady) }
        case .uploadFailed, .slow, .errorCamera, .errorMic, .errorNetwork, .errorSession,
             .errorService, .errorDevice, .interrupted, .noVoice, .exitConfirm, .stopped,
             .flashSkipped, .deny, .recoveryRequired:
            messageRoute
        }
    }

    @ViewBuilder private var messageRoute: some View {
        if let spec = MessageSpec.forRoute(route) {
            MessageScreen(
                systemImage: spec.systemImage,
                title: spec.title,
                bodyText: spec.body,
                primary: (spec.primary, primaryMessageAction),
                secondary: spec.secondary.map { ($0, secondaryMessageAction) },
                tone: spec.tone
            )
        } else {
            EmptyView()
        }
    }

    private func primaryMessageAction() {
        switch route {
        case .errorCamera, .errorDevice:
            navigation.go(.permission)
        case .errorMic, .noVoice:
            navigation.go(.voice)
        case .errorNetwork, .slow, .uploadFailed:
            navigation.go(.uploading)
        case .interrupted, .exitConfirm:
            navigation.go(.faceReady)
        default:
            finishAtBank()
        }
    }

    private func secondaryMessageAction() {
        switch route {
        case .errorDevice:
            finishAtBank()
        default:
            navigation.go(.stopped)
        }
    }

    private func finishAtBank() {
        flow.resetForBank()
        navigation.toBank()
    }
}

#if DEBUG
private struct GalleryGroup: Identifiable {
    let id = UUID()
    let title: String
    let items: [(String, Route)]
}

struct GalleryScreen: View {
    @EnvironmentObject private var navigation: AppNavigation
    @EnvironmentObject private var flow: DemoFlow
    @Environment(\.vcColors) private var colors

    private let groups = [
        GalleryGroup(title: "Bắt đầu", items: [("Màn chào", .splash), ("Đăng nhập / Đăng ký", .auth), ("Điều khoản", .terms), ("Đồng ý từng mục", .consent)]),
        GalleryGroup(title: "Danh tính", items: [
            ("Giới thiệu", .intro), ("Quyền camera, micro", .permission), ("Số điện thoại", .phone),
            ("OTP", .otp), ("OTP nhập sai", .otpError), ("CCCD mặt trước", .idFront),
            ("CCCD bị lóa", .idFrontGlare), ("Xem lại ảnh mặt trước", .idFrontReview),
            ("CCCD mặt sau", .idBack), ("Xem lại ảnh mặt sau", .idBackReview),
            ("Kiểm tra thông tin", .confirm), ("Sửa thông tin", .editInfo)
        ]),
        GalleryGroup(title: "Khuôn mặt", items: [("Chuẩn bị", .faceReady), ("Căn mặt", .framing), ("Giữ yên + nháy màu + chấm sáng", .holdStill), ("Quay đầu", .turnHead)]),
        GalleryGroup(title: "Giọng nói", items: [("Đọc câu", .voice), ("Đọc lại câu mới", .voiceAgain)]),
        GalleryGroup(title: "Kết quả", items: [
            ("Đang gửi", .uploading), ("Đang kiểm tra", .checking), ("Thành công", .success),
            ("Chờ duyệt", .review), ("Chụp lại", .retryQuality), ("Làm lại thử thách", .retryChallenge)
        ]),
        GalleryGroup(title: "Lỗi và gián đoạn", items: [
            ("Chưa cho camera", .errorCamera), ("Chưa cho micro", .errorMic), ("Mất mạng", .errorNetwork),
            ("Hết phiên", .errorSession), ("Dịch vụ không đáp ứng", .errorService), ("Thiết bị chưa đáp ứng", .errorDevice),
            ("Bị gián đoạn", .interrupted), ("Không thu được giọng", .noVoice), ("Gửi thất bại", .uploadFailed),
            ("Kiểm tra lâu", .slow), ("Xác nhận dừng", .exitConfirm), ("Đã dừng", .stopped),
            ("Bỏ qua nháy màu", .flashSkipped), ("Không thành công", .deny), ("Cần khôi phục", .recoveryRequired)
        ]),
        GalleryGroup(title: "App ngân hàng (mô phỏng)", items: [("Mở tài khoản thành công", .bankOpened)])
    ]

    var body: some View {
        VcScreen {
            Text("Tất cả màn (bản demo giao diện)")
                .font(VcType.titleMedium)
                .foregroundStyle(colors.ink)
                .accessibilityIdentifier("debug-gallery-title")
            VStack(alignment: .leading, spacing: 8) {
                Text("Luồng").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Luồng", selection: $flow.purpose) {
                    ForEach(Purpose.allCases) { purpose in Text(purpose.label).tag(purpose) }
                }
                .pickerStyle(.segmented)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Nguồn kết quả").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Nguồn kết quả", selection: $flow.useLiveAPI) {
                    Text("Giả lập trên máy").tag(false)
                    Text("API thật").tag(true)
                }
                .pickerStyle(.segmented)
                if flow.useLiveAPI {
                    VcBanner(text: "API: cấu hình Debug · kịch bản mock")
                    Picker("Kịch bản", selection: $flow.mockScenario) {
                        ForEach(flow.mockScenarios, id: \.self) { Text($0).tag($0) }
                    }
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Kết quả mô phỏng sau bước kiểm tra (chỉ khi giả lập)").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Kết quả", selection: $flow.outcome) {
                    ForEach(DemoOutcome.allCases) { Text($0.label).tag($0) }
                }
            }
            ForEach(groups) { group in
                VStack(alignment: .leading, spacing: 8) {
                    Text(group.title).font(VcType.section).foregroundStyle(colors.ink)
                    ForEach(group.items, id: \.1) { item in
                        Button {
                            flow.previewMode = true
                            navigation.go(item.1)
                        } label: {
                            HStack {
                                Text(item.0).font(VcType.bodySmall)
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption)
                            }
                            .foregroundStyle(colors.accent)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .navigationTitle("Xem tất cả màn")
    }
}
#endif
