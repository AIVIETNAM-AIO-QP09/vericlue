import AVFoundation
import SwiftUI
import UIKit

struct VoiceLiveScreen: View {
    @ObservedObject var live: LiveFlow
    @EnvironmentObject private var voice: VoiceCaptureFlow
    @EnvironmentObject private var face: FaceCaptureFlow
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.vcColors) private var colors
    @State private var screenID = UUID()
    let onRoute: (Route) -> Void
    let onClose: () -> Void

    var body: some View {
        VcScreen(step: 3) {
            VcTitleBlock(title: title, bodyText: "Giữ điện thoại ngang tầm mặt và đọc rõ câu bên dưới. Bản ghi dài tối đa 8 giây.")
            Text(live.voicePrompt ?? "Chưa nhận được câu đọc.")
                .font(VcType.titleMedium).frame(maxWidth: .infinity, alignment: .leading)
                .padding(20).background(colors.surface, in: RoundedRectangle(cornerRadius: 16))
            FrontCameraPreview(camera: voice.camera)
                .frame(width: 96, height: 128).clipShape(RoundedRectangle(cornerRadius: 14))
                .accessibilityLabel("Camera trước khi đọc câu")
            if let remaining = live.attemptsLeft {
                Text(remaining == 0 ? "Đây là lần đọc lại cuối." : "Số lần đọc lại còn lại: \(remaining)")
                    .font(VcType.caption).foregroundStyle(colors.muted)
            }
            VoiceWaveform(recorder: voice.audio, active: voice.stage == .recording)
            if let error = voice.errorText { VcBanner(text: error, tone: .warning) }
            switch voice.stage {
            case .intro, .failed, .noVoice, .interrupted:
                if voice.retryUpload {
                    VcPrimaryButton(title: "Gửi lại bản ghi") { Task { await voice.submit() } }
                } else {
                    Button { Task { await voice.start() } } label: {
                        Image(systemName: "mic.fill").font(.system(size: 30))
                            .foregroundStyle(.white).frame(width: 76, height: 76)
                            .background(colors.primary, in: Circle())
                    }
                    .accessibilityLabel("Bắt đầu đọc câu")
                    Text("Bấm micro khi đã sẵn sàng").font(VcType.caption)
                }
                if AVCaptureDevice.authorizationStatus(for: .audio) == .denied {
                    Button("Mở Cài đặt") {
                        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                    }
                }
            case .recording:
                VcPrimaryButton(title: "Đọc xong · Gửi bản ghi") { Task { await voice.finish() } }
            case .preparing, .finishing, .uploading:
                ProgressView().accessibilityLabel(title)
            case .completed: EmptyView()
            }
            #if DEBUG
            Text("IOS-04: \(face.lastFrameCount) frame · \(face.lastEvents.count) màu · \(face.lastRegionCount) mẫu vùng")
                .font(VcType.caption)
            ForEach(Array(voice.measurements.enumerated()), id: \.offset) { index, item in
                Text("Lượt \(index + 1): WAV \(item.wavSeconds.formatted(.number.precision(.fractionLength(3))))s · MP4 \(item.videoSeconds.formatted(.number.precision(.fractionLength(3))))s · offset \(item.offsetMs)ms · \(item.wavBytes)/\(item.videoBytes) bytes")
                    .font(VcType.caption).textSelection(.enabled)
            }
            #endif
            VcSecondaryButton(title: "Dừng xác minh", action: onClose)
        }
        .navigationBarBackButtonHidden(true)
        .task { voice.configure(live: live, screenID: screenID) }
        .onChange(of: voice.destination) { route in if let route { onRoute(route) } }
        .onChange(of: scenePhase) { phase in if phase != .active { voice.interrupt() } }
        .onDisappear { voice.leaveScreen(screenID) }
    }

    private var title: String {
        switch voice.stage {
        case .preparing: "Đang chuẩn bị micro"
        case .recording: "Đang thu giọng nói"
        case .finishing: "Đang hoàn tất bản ghi"
        case .uploading: "Đang gửi bản ghi"
        case .noVoice: "Chưa thu được giọng nói"
        case .interrupted: "Bản ghi bị gián đoạn"
        default: "Đọc to câu sau"
        }
    }
}

private struct VoiceWaveform: View {
    @ObservedObject var recorder: WavRecorder
    let active: Bool
    @Environment(\.vcColors) private var colors
    var body: some View {
        VStack(spacing: 10) {
            HStack(alignment: .center, spacing: 5) {
                ForEach(0..<21) { index in
                    let envelope = 1 - abs(Double(index - 10)) / 12
                    Capsule().fill(colors.primary)
                        .frame(width: 5, height: active ? max(4, recorder.meter.level * 64 * envelope) : 4)
                }
            }.frame(height: 64)
            Text(active ? "\(recorder.meter.seconds.formatted(.number.precision(.fractionLength(1)))) / 8 giây" : "Micro chỉ bật khi bạn bấm bắt đầu")
                .font(VcType.caption).foregroundStyle(colors.muted)
        }.accessibilityLabel(active ? "Mức âm thanh đang thu" : "Chưa thu âm")
    }
}
