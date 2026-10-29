import SwiftUI
import AVFoundation

struct RouteScreen: View {
    let route: Route
    @EnvironmentObject private var navigation: AppNavigation
    @EnvironmentObject private var flow: DemoFlow
    @EnvironmentObject private var identity: IdentityFlow
    @EnvironmentObject private var face: FaceCaptureFlow
    @EnvironmentObject private var voice: VoiceCaptureFlow
    @EnvironmentObject private var captures: CaptureFlows
    @State private var authTask: Task<Void, Never>?
    @State private var authBusy = false

    private var usesLiveIdentity: Bool { flow.useLiveAPI && !flow.previewMode }

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
                onRegister: { beginIdentity(.onboarding) },
                onLogin: { beginIdentity(.reauth) },
                onRecover: { beginIdentity(.recovery) }
            )
            .disabled(authBusy)
            .overlay { if authBusy { ProgressView("Đang chuẩn bị…") } }
            .onDisappear {
                if authTask != nil { authTask?.cancel(); authTask = nil; authBusy = false; identity.cancelPendingRequests() }
            }
        case .terms:
            TermsScreen(onAccept: { navigation.go(.phone) })
                .safeAreaInset(edge: .top) {
                    if usesLiveIdentity, let hint = identity.accountHint { VcBanner(text: hint).padding(.horizontal, 20) }
                }
        case .phone:
            if usesLiveIdentity { IdentityPhoneScreen(onNext: followIdentity) }
            else { PhoneScreen { _ in navigation.go(.otp) } }
        case .otp:
            if usesLiveIdentity { IdentityOTPScreen(onNext: followIdentity, onRestart: finishAtBank) }
            else { OTPDemoScreen { navigation.go(flow.afterOTP()) } }
        case .otpError:
            OTPDemoScreen(startsWithError: true) { navigation.go(flow.afterOTP()) }
        case .idFront:
            if usesLiveIdentity { IdentityCaptureScreen(isBack: false, onNext: followIdentity).id(identity.frontCaptureID) }
            else { IDCaptureScreen(isBack: false, onCapture: { navigation.go(.idBack) }) }
        case .idFrontGlare:
            IDCaptureScreen(isBack: false, glare: true, onCapture: { navigation.replaceTop(with: .idFront) })
        case .idBack:
            if usesLiveIdentity { IdentityCaptureScreen(isBack: true, onNext: followIdentity).id(identity.backCaptureID) }
            else { IDCaptureScreen(isBack: true, onCapture: { navigation.go(.idReview) }) }
        case .idReview:
            if usesLiveIdentity { IdentityReviewScreen(onNext: followIdentity) }
            else { IDPairDemoReviewScreen(onContinue: { navigation.go(.faceReady) }, onRetake: { navigation.returnTo($0) }) }
        case .confirm:
            if usesLiveIdentity { IdentityConfirmScreen(onNext: followIdentity) }
            else { ConfirmInfoScreen(onCorrect: { navigation.go(flow.confirmIdentity()) }, onEdit: { navigation.go(.editInfo) }) }
        case .editInfo:
            if usesLiveIdentity { IdentityEditScreen(onNext: followIdentity) }
            else { EditInfoScreen(onSave: { navigation.go(flow.confirmIdentity()) }, onRetake: { flow.idConfirmed = false; navigation.go(.idFront) }) }
        case .faceReady:
            if usesLiveIdentity {
                liveFaceScreen
            } else {
                FaceReadyScreen(onReady: { navigation.go(.framing) }, onSkipFlash: { navigation.go(.flashSkipped) })
            }
        case .framing:
            if usesLiveIdentity { liveFaceScreen }
            else { FramingScreen(onCaptured: { navigation.go(.holdStill) }) }
        case .holdStill:
            if usesLiveIdentity { liveFaceScreen }
            else { FaceTimelineDemoScreen(onStop: { navigation.go(.exitConfirm) }, onDone: { navigation.go(.turnHead) }) }
        case .turnHead:
            if usesLiveIdentity { liveFaceScreen }
            else { TurnHeadScreen(onDone: { navigation.go(flow.afterHeadTurn()) }) }
        case .voice:
            if usesLiveIdentity { liveVoiceScreen }
            else { VoiceScreen(onFinished: { navigation.go(.uploading) }) }
        case .voiceAgain:
            if usesLiveIdentity { liveVoiceScreen }
            else { VoiceScreen(again: true) {
                flow.outcome = .pass
                navigation.go(.uploading)
            } }
        case .uploading:
            if usesLiveIdentity {
                FacePendingUploadScreen(onRoute: { navigation.replaceTop(with: $0) }, onClose: requestCaptureExit)
            } else {
            UploadingScreen(
                onStop: { navigation.go(.exitConfirm) },
                onDone: { navigation.replaceTop(with: .checking) },
                autoAdvance: !flow.previewMode && !usesLiveIdentity
            )
            }
        case .checking:
            CheckingScreen(
                purpose: flow.purpose,
                onDone: { navigation.replaceTop(with: flow.outcome.destination) },
                autoAdvance: !flow.previewMode && !usesLiveIdentity
            )
        case .success:
            SuccessScreen(purpose: flow.purpose,
                          voiceChecked: usesLiveIdentity ? identity.liveFlow?.voiceChecked == true : true,
                          liveVerification: usesLiveIdentity) {
                if flow.purpose == .onboarding { navigation.go(.bankOpened) }
                else { finishAtBank() }
            }
            .onAppear {
                if usesLiveIdentity { identity.liveFlow?.collectReceiptAfterPass() }
            }
        case .review:
            ReviewScreen(onBank: finishAtBank)
        case .retryQuality:
            if usesLiveIdentity, let live = identity.liveFlow {
                LiveFaceRetryScreen(live: live, onRetry: { navigation.restartFace() }, quality: true)
            } else { RetryQualityScreen { flow.outcome = .pass; navigation.go(.faceReady) } }
        case .retryChallenge:
            if usesLiveIdentity, let live = identity.liveFlow {
                LiveFaceRetryScreen(live: live, onRetry: { navigation.restartFace() }, quality: false)
            } else { RetryChallengeScreen { flow.outcome = .pass; navigation.go(.faceReady) } }
        case .uploadFailed, .slow, .errorCamera, .errorMic, .errorNetwork, .errorSession,
             .errorService, .errorDevice, .interrupted, .faceExpired, .noVoice, .exitConfirm, .stopped,
             .flashSkipped, .deny, .recoveryRequired:
            messageRoute
        }
    }

    private var liveFaceScreen: some View {
        FaceLiveScreen(live: identity.liveFlow, purpose: flow.purpose,
                       onRoute: { navigation.replaceTop(with: $0) }, onClose: requestCaptureExit)
            .environment(\.vcCameraLayout, true)
    }

    @ViewBuilder private var liveVoiceScreen: some View {
        if let live = identity.liveFlow {
            VoiceLiveScreen(live: live, onRoute: { navigation.replaceTop(with: $0) }, onClose: requestCaptureExit)
                .environment(\.vcCameraLayout, true)
        }
        else { MessageScreen(systemImage: "wifi.exclamationmark", title: "Chưa thể tiếp tục",
                             bodyText: "Chưa kết nối được phiên xác minh. Hãy bắt đầu lại.",
                             primary: ("Quay lại ứng dụng ngân hàng", finishAtBank)) }
    }

    @ViewBuilder private var messageRoute: some View {
        if usesLiveIdentity, [.errorCamera, .errorMic].contains(route), let spec = MessageSpec.forRoute(route) {
            MessageScreen(systemImage: spec.systemImage, title: spec.title, bodyText: spec.body,
                primary: ("Mở Cài đặt", openCameraSettings), secondary: ("Thử lại", {
                    let cameraAllowed = AVCaptureDevice.authorizationStatus(for: .video) == .authorized
                    let micAllowed = route != .errorMic || AVCaptureDevice.authorizationStatus(for: .audio) == .authorized
                    guard cameraAllowed && micAllowed else { openCameraSettings(); return }
                    captures.restartFace(live: identity.liveFlow)
                    navigation.returnTo(.faceReady)
                }), tone: spec.tone)
        } else if let spec = MessageSpec.forRoute(route) {
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
            openCameraSettings()
        case .errorMic:
            openCameraSettings()
        case .noVoice:
            if usesLiveIdentity {
                captures.restartFace(live: identity.liveFlow)
                navigation.returnTo(.faceReady)
            } else { navigation.go(.voice) }
        case .errorNetwork, .slow, .uploadFailed:
            navigation.go(.uploading)
        case .interrupted, .faceExpired, .exitConfirm:
            if usesLiveIdentity {
                captures.restartFace(live: identity.liveFlow)
                navigation.restartFace()
            } else { navigation.go(.faceReady) }
        default:
            finishAtBank()
        }
    }

    private func secondaryMessageAction() {
        if usesLiveIdentity { finishAtBank(); return }
        switch route {
        case .errorDevice:
            finishAtBank()
        default:
            navigation.go(.stopped)
        }
    }

    private func finishAtBank() {
        captures.leaveFlow(live: identity.liveFlow)
        identity.reset()
        flow.resetForBank()
        navigation.toBank()
    }

    private func requestCaptureExit() { captures.showExitConfirmation = true }

    private func beginIdentity(_ purpose: Purpose) {
        guard !authBusy else { return }
        flow.idConfirmed = false
        if !usesLiveIdentity {
            flow.purpose = purpose
            navigation.go(purpose == .onboarding ? .terms : .phone)
            return
        }
        captures.leaveFlow(live: identity.liveFlow)
        authBusy = true
        authTask = Task {
            let entry = await identity.beginAccount(purpose: purpose, scenario: flow.mockScenario)
            guard !Task.isCancelled else { return }
            authTask = nil; authBusy = false
            guard let entry else { navigation.go(.errorService); return }
            flow.purpose = entry.purpose
            navigation.go(entry.route)
        }
    }

    private func followIdentity(_ route: Route) {
        switch route {
        case .idFront, .idBack, .idReview, .confirm: navigation.returnTo(route)
        default: navigation.go(route)
        }
    }
}
