import CoreGraphics
import CoreMedia
import Foundation
import SwiftUI

// Reuse the root-owned camera, including Debug checkpoints. Never a second session.
struct FaceCameraCheckpointScreen: View {
    let onClose: () -> Void
    @ObservedObject private var camera: FrontCameraSession
    @Environment(\.scenePhase) private var scenePhase
    @State private var phase = 0
    @State private var share: VideoShareItem?
    private let phases = ["Baseline", "Màu", "Chấm sáng", "Quay đầu"]

    init(camera: FrontCameraSession, onClose: @escaping () -> Void) {
        self.camera = camera
        self.onClose = onClose
    }

    var body: some View {
        VcScreen(step: 2) {
            VcTitleBlock(title: "Kiểm tra camera trước", bodyText: "IOS-04 · checkpoint 5.4")
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(phases[phase]).font(VcType.titleMedium)
                    Text(camera.receivingFrames ? "Đang nhận khung hình" : "Đang chờ camera")
                        .font(VcType.bodySmall)
                    Text("Preview lật gương; khung dữ liệu không lật.").font(VcType.caption)
                }
                Spacer(minLength: 0)
                // Stable position/identity while the phase LABEL changes. No timeline yet.
                FrontCameraPreview(camera: camera)
                    .frame(width: 96, height: 128)
                    .clipped()
                    .accessibilityIdentifier("front-camera-preview")
            }
            if camera.failure == nil {
                Text(camera.snapshot?.quality.state.guidance ?? "Đưa khuôn mặt vào khung")
                    .font(VcType.titleMedium)
                    .accessibilityIdentifier("face-quality-guidance")
                ProgressView(value: (camera.snapshot?.quality.heldMs ?? 0) / QualityGate.goodHoldMs)
                    .accessibilityLabel("Giữ đạt liên tục một giây")
            }
            if camera.snapshot?.quality.ready == true {
                VcBanner(text: "Đã đủ điều kiện căn mặt. Có thể ghi video kiểm tra.")
            }
            VcBanner(text: "Video kiểm tra chỉ lưu tạm trên iPhone, không có tiếng và chưa gửi server. Chưa chạy lịch xác minh; không đưa video khuôn mặt vào Git.")
            recordingControls
            if camera.starting { ProgressView("Đang mở camera…") }
            if let failure = camera.failure {
                VcBanner(text: failureText(failure), tone: .warning)
                Button("Mở Cài đặt", action: openCameraSettings).font(VcType.label)
                Button("Thử lại") { Task { await camera.start() } }
                    .disabled(camera.starting || camera.running)
            }
            Button("Đổi pha kiểm tra") { phase = (phase + 1) % phases.count }
                .font(VcType.label)
                .disabled(!camera.receivingFrames)
                .accessibilityIdentifier("front-camera-change-phase")
            #if DEBUG
            diagnostics
            #endif
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcSecondaryButton(title: "Đóng kiểm tra camera", action: {
                    camera.stop()
                    camera.discardRecording()
                    onClose()
                })
            }
        }
        .task(id: scenePhase) {
            if scenePhase == .active { await camera.start() }
            else { camera.stop() }
        }
        .onDisappear {
            camera.stop()
            if share == nil { camera.discardRecording() }
        }
        .sheet(item: $share) { item in VideoShareSheet(url: item.url) }
    }

    private var recordingControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            if camera.recording {
                Text("Đang ghi MP4…").font(VcType.label)
                VcPrimaryButton(title: "Dừng và hoàn tất MP4", action: { Task { await camera.finishRecording() } })
                    .accessibilityIdentifier("front-camera-finish-recording")
            } else if camera.finishing {
                ProgressView("Đang hoàn tất và kiểm tra MP4…")
            } else {
                VcPrimaryButton(title: "Ghi video kiểm tra (5.4)", action: { Task { await camera.startRecording() } },
                    enabled: camera.receivingFrames && camera.snapshot?.quality.ready == true)
                    .accessibilityIdentifier("front-camera-start-recording")
            }
            if let failure = camera.recordingError { VcBanner(text: recordingFailureText(failure), tone: .warning) }
            if let video = camera.recordedVideo, let inspection = camera.inspection {
                Text("MP4 đã hoàn tất · H.264 · không tiếng").font(VcType.label)
                Text("\(inspection.width)×\(inspection.height) · \(inspection.seconds, specifier: "%.2f") giây · \(inspection.bytes) byte")
                    .font(VcType.caption)
                Text("Frame đã ghi: \(video.frameTimes.count) · bỏ do writer bận: \(video.backpressureDrops)")
                    .font(VcType.caption)
                Button("Xuất MP4 để mở QuickTime") { share = VideoShareItem(url: video.url) }
                    .font(VcType.label)
                    .disabled(camera.recording || camera.finishing)
                    .accessibilityIdentifier("front-camera-export-video")
                Button("Xóa video tạm", action: camera.discardRecording).font(VcType.label)
                    .disabled(camera.recording || camera.finishing)
            }
        }
    }

    private func recordingFailureText(_ failure: VideoWriterError) -> String {
        switch failure {
        case .qualityLost: "Điều kiện căn mặt đã thay đổi. Hãy căn lại rồi ghi."
        case .cancelled: "Đã hủy đoạn ghi bị gián đoạn. Hãy căn mặt rồi ghi lại."
        case .noFrames: "Đoạn ghi chưa có khung hình. Hãy ghi lại."
        case .frameGap: "Video bị gián đoạn khung hình. Hãy căn mặt rồi ghi lại; đoạn này chưa được gửi."
        case .tooLong: "Đoạn kiểm tra vượt giới hạn 60 giây. Hãy ghi lại đoạn ngắn hơn."
        default: "Chưa hoàn tất được MP4. Hãy căn mặt rồi ghi lại; đoạn này chưa được gửi."
        }
    }

    #if DEBUG
    private var diagnostics: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Chẩn đoán 5.1–5.4 (chỉ Debug)").font(VcType.label)
            Text("Pipeline: \(camera.pipelineID)")
            Text("Session: \(camera.sessionID)")
            Text("Output: \(camera.outputID)")
            Text("Preview: \(camera.previewID)")
            if let snapshot = camera.snapshot {
                Text("Cấu hình: \(snapshot.configurations) · input: \(snapshot.inputs) · output: \(snapshot.outputs)")
                Text("Frame: \(snapshot.meter.frames) · drop: \(snapshot.meter.droppedFrames)")
                Text("\(snapshot.meter.width)×\(snapshot.meter.height) · \(snapshot.meter.fps, specifier: "%.1f") fps")
                Text("Dữ liệu dọc: \(snapshot.portrait ? "có" : "không") · mirror: \(snapshot.mirrored ? "có" : "không")")
                if let tracking = snapshot.tracking {
                    Text("Vision cách 1 frame · \(tracking.elapsedMs, specifier: "%.1f") ms")
                    if let face = tracking.signal {
                        Text("Số mặt: \(face.faces) · luma: \(face.brightness, specifier: "%.1f")")
                        Text("yaw: \(angle(face.yaw)) · roll: \(angle(face.roll)) · pitch: \(angle(face.pitch))")
                        if let box = face.box {
                            Text("Box x/y/w/h: \(box.minX, specifier: "%.2f") / \(box.minY, specifier: "%.2f") / \(box.width, specifier: "%.2f") / \(box.height, specifier: "%.2f")")
                        }
                    }
                    if let code = tracking.errorCode { Text("Vision lỗi: \(tracking.errorDomain ?? "unknown") / \(code)") }
                }
                Text("Giữ đạt: \(snapshot.quality.heldMs, specifier: "%.0f") ms")
                Text("Writer: \(snapshot.recording.phase.rawValue) · frame: \(snapshot.recording.frames) · \(snapshot.recording.elapsed, specifier: "%.2f") giây")
            }
            if let video = camera.recordedVideo {
                Text("t0 PTS: \(video.firstPTS.seconds, specifier: "%.6f") · frame_times: \(video.frameTimes.count)")
                Text("media_time đầu: \(video.frameTimes.first?.mediaTime ?? -1, specifier: "%.6f") giây")
            }
        }
        .font(VcType.caption)
        .textSelection(.enabled)
        .accessibilityIdentifier("front-camera-diagnostics")
    }

    private func angle(_ degrees: Double?) -> String {
        degrees.map {
            $0.formatted(.number.precision(.fractionLength(1)).sign(strategy: .always(includingZero: true))) + "°"
        } ?? "không có"
    }
    #endif

    private func failureText(_ failure: FrontCameraError) -> String {
        switch failure {
        case .denied: "Hãy cho phép dùng camera trong Cài đặt rồi thử lại."
        case .unsupportedConfiguration: "Thiết bị chưa hỗ trợ cấu hình camera cần dùng."
        case .noFrames: "Chưa nhận được khung hình. Hãy đóng ứng dụng khác đang dùng camera rồi thử lại."
        case .unavailable: "Camera trước chưa hoạt động. Simulator không thay được kiểm tra trên iPhone thật."
        }
    }
}
