import AVFoundation
import Combine
import Foundation
import QuartzCore
import UIKit

struct VoiceCaptureMeasurement: Sendable {
    let sessionID: String
    let wavSeconds: Double
    let videoSeconds: Double
    let offsetMs: Int
    let wavBytes: Int
    let videoBytes: Int64
}

@MainActor
final class VoiceCaptureFlow: ObservableObject {
    enum Stage { case intro, preparing, recording, finishing, uploading, failed, noVoice, interrupted, completed }
    let camera: FrontCameraSession
    let audio = WavRecorder()
    @Published private(set) var stage = Stage.intro
    @Published private(set) var errorText: String?
    @Published private(set) var destination: Route?
    @Published private(set) var retryUpload = false
    @Published private(set) var measurements: [VoiceCaptureMeasurement] = []
    private var live: LiveFlow?
    private var generation = 0
    private var videoHost: Double?
    private var payload: (wav: Data, video: Data, offset: Int)?
    private var watchdog: Task<Void, Never>?
    private var subscriptions = Set<AnyCancellable>()
    private var oldIdleDisabled: Bool?
    private var screenID: UUID?

    init(camera: FrontCameraSession) {
        self.camera = camera
        audio.$meter.sink { [weak self] meter in
            guard let self, self.stage == .recording else { return }
            if meter.failure != nil { self.failCapture(.invalidClock) }
            else if meter.limitReached { Task { await self.finish() } }
        }.store(in: &subscriptions)
        camera.$recordingError.sink { [weak self] error in
            guard let self, error != nil, [.preparing, .recording].contains(self.stage) else { return }
            self.failCapture(.interrupted)
        }.store(in: &subscriptions)
        for name in [AVAudioSession.interruptionNotification, AVAudioSession.routeChangeNotification,
                     AVAudioSession.mediaServicesWereResetNotification, .AVAudioEngineConfigurationChange] {
            NotificationCenter.default.publisher(for: name).receive(on: DispatchQueue.main).sink { [weak self] _ in
                // Never silently restart a partial A/V recording after an interruption.
                guard let self, self.stage == .recording else { return }
                self.interrupt()
            }.store(in: &subscriptions)
        }
    }

    func configure(live: LiveFlow?, screenID: UUID) {
        cancel()
        self.screenID = screenID
        self.live = live
        destination = nil; errorText = nil; stage = .intro
    }

    func start() async {
        guard [.intro, .failed, .noVoice, .interrupted].contains(stage), !retryUpload else { return }
        guard let live, !(live.voicePrompt ?? "").isEmpty, !(live.voiceChallengeId ?? "").isEmpty else {
            failCapture(.unavailable); return
        }
        generation += 1
        let id = generation
        stage = .preparing; errorText = nil; destination = nil; payload = nil; videoHost = nil
        camera.discardRecording()
        oldIdleDisabled = UIApplication.shared.isIdleTimerDisabled
        UIApplication.shared.isIdleTimerDisabled = true
        do {
            try await audio.prepare()
            try check(id)
            await camera.start() // Reuses the SAME session if already running.
            let deadline = CACurrentMediaTime() + 5
            while !camera.receivingFrames {
                try check(id)
                guard camera.running, CACurrentMediaTime() < deadline else { throw WavError.unavailable }
                try await Task.sleep(for: .milliseconds(20))
            }
            try check(id)
            await camera.startRecording(forVoice: true)
            let firstDeadline = CACurrentMediaTime() + 3
            while true {
                try check(id)
                guard camera.recording, CACurrentMediaTime() < firstDeadline else { throw WavError.unavailable }
                if let snapshot = camera.snapshot, snapshot.recordingID == camera.recordingAttemptID,
                   snapshot.recording.frames > 0, let host = snapshot.firstHostSeconds {
                    videoHost = host; break
                }
                try await Task.sleep(for: .milliseconds(10))
            }
            // Only now may the engine deliver PCM for the WAV.
            try await audio.start()
            try check(id)
            stage = .recording
            let armed = CACurrentMediaTime()
            watchdog = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(50))
                    guard let self, id == self.generation, self.stage == .recording else { return }
                    let now = CACurrentMediaTime()
                    if let first = self.audio.meter.firstHostSeconds {
                        // finish cancels the watchdog; do not cancel its own task
                        // and then accidentally abandon the awaited file closure.
                        if now - first >= 8 { Task { await self.finish() }; return }
                        if now - first - self.audio.meter.seconds > 0.3 { self.failCapture(.interrupted); return }
                        if !self.camera.receivingFrames { self.failCapture(.interrupted); return }
                    } else if now - armed >= 3 { self.failCapture(.empty); return }
                }
            }
        } catch {
            guard id == generation else { return }
            failCapture((error as? WavError) ?? .unavailable)
        }
    }

    private func check(_ id: Int) throws {
        guard generation == id, !Task.isCancelled, stage == .preparing else { throw WavError.cancelled }
    }

    func finish() async {
        guard stage == .recording else { return }
        stage = .finishing
        watchdog?.cancel(); watchdog = nil
        let id = generation
        do {
            // Close WAV first, then finish the silent MP4 so it covers all audio.
            let wav = try await audio.finish()
            guard id == generation, !Task.isCancelled else { return }
            await camera.finishRecording()
            guard id == generation, !Task.isCancelled else { return }
            guard let video = camera.recordedVideo, let inspection = camera.inspection,
                  let videoHost else { throw WavError.interrupted }
            let offset = try WavPCM.offsetMs(audioHost: wav.firstHostSeconds, videoHost: videoHost)
            // Allow one 30fps boundary; reject uncovered audio rather than upload it.
            guard wav.seconds > 0, wav.seconds <= 8,
                  Double(offset) / 1000 + wav.seconds <= inspection.seconds + 0.1 else { throw WavError.invalidClock }
            let bytes = try await Task.detached(priority: .userInitiated) { try Data(contentsOf: video.url) }.value
            guard id == generation, !Task.isCancelled else { return }
            guard !bytes.isEmpty else { throw WavError.empty }
            measurements.append(VoiceCaptureMeasurement(sessionID: live?.session?.sessionId ?? "không có phiên",
                wavSeconds: wav.seconds, videoSeconds: inspection.seconds,
                offsetMs: offset, wavBytes: wav.data.count, videoBytes: inspection.bytes))
            if measurements.count > 3 { measurements.removeFirst(measurements.count - 3) }
            payload = (wav.data, bytes, offset)
            restoreIdle()
            await submit()
        } catch { if id == generation { failCapture((error as? WavError) ?? .interrupted) } }
    }

    func submit() async {
        guard [.failed, .finishing].contains(stage), let live, let payload else { return }
        let id = generation
        stage = .uploading; errorText = nil; retryUpload = false
        let next = await live.submitVoice(wav: payload.wav, video: payload.video, audioOffsetMs: payload.offset,
                                          onAccepted: { self.camera.discardRecording() })
        guard id == generation, !Task.isCancelled else { return }
        switch next {
        case .to(let route):
            self.payload = nil; camera.discardRecording()
            stage = .completed
            // Keep the same camera graph for a newly issued read-again prompt.
            if route != .voiceAgain { camera.stop() }
            destination = route
        case .fail(.network):
            stage = .failed; retryUpload = true
            errorText = "Không kết nối được. Kiểm tra kết nối mạng rồi thử gửi lại."
        case .fail(let error):
            stage = .failed; self.payload = nil; camera.stop(); camera.discardRecording()
            errorText = "Chưa gửi được bản ghi. Vui lòng bắt đầu lại."
            destination = FlowRules.errorRoute(error)
        }
    }

    private func failCapture(_ error: WavError) {
        generation += 1
        stage = error == .empty ? .noVoice : .failed // Before synchronous camera notifications.
        watchdog?.cancel(); watchdog = nil
        audio.cancel(); camera.stop(); camera.discardRecording(); restoreIdle()
        payload = nil; retryUpload = false
        switch error {
        case .denied: errorText = "Chưa cho phép dùng micro. Hãy mở Cài đặt để cấp quyền rồi thử lại."
        case .empty: errorText = "Chưa thu được giọng nói. Hãy đọc rõ câu trên màn hình rồi thử lại."
        default: errorText = "Bản ghi bị gián đoạn hoặc chưa đầy đủ. Hãy giữ điện thoại ổn định rồi đọc lại."
        }
    }

    func interrupt() {
        if retryUpload { camera.stop(); return } // Preserve the sealed upload payload.
        guard [.intro, .preparing, .recording, .finishing, .noVoice, .failed].contains(stage) else { return }
        failCapture(.interrupted)
        stage = .interrupted
    }

    func cancel() {
        generation += 1
        let active = [.preparing, .recording, .finishing, .uploading].contains(stage) || retryUpload
        stage = .intro
        watchdog?.cancel(); watchdog = nil
        audio.cancel()
        if active { camera.stop(); camera.discardRecording() }
        payload = nil; videoHost = nil; retryUpload = false; restoreIdle()
    }

    func leaveScreen(_ id: UUID) {
        guard screenID == id else { return }
        if stage != .completed { cancel(); camera.stop(); camera.discardRecording() }
    }

    private func restoreIdle() {
        if let oldIdleDisabled { UIApplication.shared.isIdleTimerDisabled = oldIdleDisabled; self.oldIdleDisabled = nil }
    }
}
