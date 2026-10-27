import Combine
import CoreMedia
import Foundation
import QuartzCore
import UIKit

@MainActor
private final class FaceDisplayTarget: NSObject {
    weak var owner: FaceCaptureFlow?
    @objc func tick(_ link: CADisplayLink) { owner?.displayFrame(targetSeconds: link.targetTimestamp) }
}

@MainActor
final class FaceCaptureFlow: ObservableObject {
    enum Stage {
        case intro, preparing, framing, recording, finishing, uploading, failed, interrupted, awaitingVoice, completed
        var restartsOnInterruption: Bool { [.preparing, .framing, .recording, .finishing, .awaitingVoice].contains(self) }
    }
    let camera = FrontCameraSession()
    @Published private(set) var stage = Stage.intro
    @Published private(set) var phase = FaceTimeline.Phase.baseline
    @Published private(set) var errorText: String?
    @Published private(set) var destination: Route?
    @Published private(set) var retryUpload = false
    @Published private(set) var elapsedMs = 0.0
    @Published private(set) var lastQuality: [String: JSONValue] = [:]
    @Published private(set) var lastEvents: [ColorEvent] = []
    @Published private(set) var lastFrameCount = 0
    @Published private(set) var lastRegionCount = 0
    @Published private(set) var lastAttemptChallengeId: String?
    weak var canvas: FaceTimelineCanvasView?
    private var live: LiveFlow?
    private var purpose = Purpose.onboarding
    private var timeline: FaceTimeline?
    private var eventLog = ColorEventLog()
    private var events: [ColorEvent] { eventLog.events }
    private var subscriptions = Set<AnyCancellable>()
    private var displayLink: CADisplayLink?
    private let displayTarget = FaceDisplayTarget()
    private var oldBrightness: CGFloat?
    private var oldIdleDisabled: Bool?
    private var armedAt = 0.0
    private var lastDisplay: Double?
    private var generation = 0
    private var payload: (Data, FaceEvidence, CamProbe, [String: JSONValue])?
    private var screenID: UUID?

    init() {
        displayTarget.owner = self
        camera.$snapshot.sink { [weak self] snapshot in
            guard let self, self.stage == .framing, snapshot?.quality.ready == true else { return }
            self.stage = .recording // Prevent repeated start tasks from successive frames.
            Task { await self.startRecording() }
        }.store(in: &subscriptions)
        camera.$recordingError.sink { [weak self] error in
            guard let self, error != nil, self.stage == .recording else { return }
            self.captureFailed()
        }.store(in: &subscriptions)
        camera.$failure.sink { [weak self] failure in
            guard let self, let failure, [.preparing, .framing, .recording, .finishing].contains(self.stage) else { return }
            self.interrupt(route: failure == .denied ? .errorCamera : .interrupted)
        }.store(in: &subscriptions)
        camera.$receivingFrames.dropFirst().sink { [weak self] receiving in
            guard let self, !receiving, self.camera.running,
                  [.framing, .recording].contains(self.stage) else { return }
            self.interrupt()
        }.store(in: &subscriptions)
    }

    func configure(live: LiveFlow?, purpose: Purpose, screenID: UUID? = nil) {
        generation += 1
        self.screenID = screenID
        stage = .intro
        camera.stop(); camera.discardRecording()
        invalidateDisplay()
        self.live = live; self.purpose = purpose
        destination = nil; errorText = nil; retryUpload = false; payload = nil
        phase = .baseline; stage = .intro; timeline = nil; elapsedMs = 0
        eventLog = ColorEventLog(); lastEvents = []; lastQuality = [:]; lastFrameCount = 0; lastRegionCount = 0
        lastAttemptChallengeId = nil
    }

    func prepare() async {
        guard [.intro, .failed, .interrupted].contains(stage), !retryUpload else { return }
        guard let live else { stage = .failed; errorText = "Chưa kết nối được phiên xác minh. Hãy bắt đầu lại."; return }
        generation += 1
        let id = generation
        stage = .preparing; errorText = nil
        camera.stop(); camera.discardRecording()
        if let error = await live.prepareFace() {
            guard id == generation, !Task.isCancelled else { return }
            apiFailed(error, canRetryUpload: false)
            return
        }
        guard id == generation, !Task.isCancelled, let challenge = live.challenge else { return }
        do {
            if purpose != .reauth {
                guard let d = challenge.dynamic, d.sessionId == live.session?.sessionId,
                      d.nonce == live.session?.nonce else { throw FaceTimelineError.invalidChallenge }
            }
            timeline = try FaceTimeline(challenge: challenge, passive: purpose == .reauth)
            eventLog = ColorEventLog(); payload = nil; elapsedMs = 0; phase = .baseline
            canvas?.paint(rgb: FaceTimeline.grey, dot: nil)
            await camera.start()
            guard id == generation, !Task.isCancelled else { return }
            guard camera.running else {
                stage = .failed
                errorText = camera.failure == .denied ? "Chưa cho phép dùng camera. Hãy mở Cài đặt để cấp quyền." : "Chưa mở được camera. Hãy thử lại."
                destination = camera.failure == .denied ? .errorCamera : .errorDevice
                return
            }
            stage = .framing
        } catch {
            guard id == generation else { return }
            stage = .failed; errorText = "Chưa nhận được lịch xác minh hợp lệ. Hãy thử lại."
        }
    }

    private func startRecording() async {
        guard let timeline, stage == .recording else { return }
        let id = generation
        oldBrightness = UIScreen.main.brightness
        oldIdleDisabled = UIApplication.shared.isIdleTimerDisabled
        UIScreen.main.brightness = 1
        UIApplication.shared.isIdleTimerDisabled = true
        canvas?.paint(rgb: FaceTimeline.grey, dot: nil)
        armedAt = CACurrentMediaTime(); lastDisplay = nil
        let link = CADisplayLink(target: displayTarget, selector: #selector(FaceDisplayTarget.tick(_:)))
        link.preferredFrameRateRange = CAFrameRateRange(minimum: 30, maximum: 60, preferred: 60)
        displayLink = link
        link.add(to: .main, forMode: .common)
        await camera.startRecording(timeline: timeline)
        guard id == generation, stage == .recording else { return }
        if !camera.recording { captureFailed() }
    }

    fileprivate func displayFrame(targetSeconds now: Double) {
        guard stage == .recording, let timeline else { return }
        guard now.isFinite, lastDisplay.map({ now > $0 && now - $0 <= 0.1 }) ?? true else { captureFailed(); return }
        lastDisplay = now
        guard let first = camera.snapshot?.firstHostSeconds else {
            if now - armedAt > 3 { captureFailed() }
            return
        }
        let t = (now - first) * 1000
        guard t >= 0, t <= Double(timeline.endMs) + 300 else { captureFailed(); return }
        let p = timeline.phase(atMs: t)
        let dot: CGPoint?
        if case .gaze(let x, let y) = p { dot = CGPoint(x: x, y: y) } else { dot = nil }
        guard let canvas, canvas.window != nil else { captureFailed(); return }
        // Direct CALayer updates in the display callback, not SwiftUI animation/timer.
        canvas.paint(rgb: timeline.background(atMs: t), dot: dot)
        if case .color(let index) = p, events.last?.index != index {
            do { try eventLog.record(index: index, rgb: timeline.colors[index].rgb, targetSeconds: now) }
            catch { captureFailed(); return }
        }
        // Do not trigger 60 SwiftUI layout passes per second for dot interpolation.
        if phaseLabelKey(p) != phaseLabelKey(phase) { phase = p }
        if abs(t - elapsedMs) >= 100 { elapsedMs = t }
        if p == .done, let recorded = camera.snapshot?.recording,
           recorded.elapsed * 1000 >= Double(timeline.endMs) {
            guard events.count == timeline.colors.count else { captureFailed(); return }
            stage = .finishing
            invalidateDisplay()
            Task { await finishAndSubmit() }
        }
    }

    private func phaseLabelKey(_ p: FaceTimeline.Phase) -> String {
        switch p {
        case .baseline: "baseline"
        case .color(let i): "color_\(i)"
        case .gap: "gap"
        case .gaze: "gaze"
        case .head(let i, _): "head_\(i)"
        case .done: "done"
        }
    }

    private func finishAndSubmit() async {
        let id = generation
        await camera.finishRecording()
        guard id == generation, !Task.isCancelled, stage == .finishing else { return }
        guard let video = camera.recordedVideo, let inspection = camera.inspection, let timeline,
              abs(video.lastPTS.seconds - video.firstPTS.seconds - Double(timeline.endMs) / 1000) <= 0.1 else {
            captureFailed(); return
        }
        do {
            let evidence = try await camera.faceEvidence()
            guard !evidence.frameTimes.isEmpty, abs(evidence.frontalAtMs - Double(timeline.frontalAtMs)) <= 100,
                  evidence.regionMeans.contains(where: Regions.hasAllSixMeasured),
                  evidence.duplicateRatio != nil else { throw FaceTimelineError.missingEvidence }
            let data = try await Task.detached(priority: .userInitiated) { try Data(contentsOf: video.url) }.value
            guard id == generation, !Task.isCancelled, !data.isEmpty else { return }
            var probe = DeviceProbe.collect()
            probe.duplicateFrameRatio = evidence.duplicateRatio
            probe.trackSettings = ["width": .number(Double(video.width)), "height": .number(Double(video.height)),
                                   "mirrored": .bool(false), "camera": .string("front")]
            let seconds = video.lastPTS.seconds - video.firstPTS.seconds
            var quality: [String: JSONValue] = [
                "client": .string("ios"), "clock": .string("CACurrentMediaTime"),
                "timestamp_source": .string("sample_buffer_pts_converted_to_host_clock"),
                "fps": .number(seconds > 0 ? Double(video.frameTimes.count - 1) / seconds : 0),
                "has_video": .bool(true), "ae_awb_locked": .bool(evidence.aeAwbLocked),
                "debugger_probe": .string(DeviceProbe.debuggerNote), "frontal_at_ms": .number(evidence.frontalAtMs),
                "pts_to_host_offset_ms": .number(evidence.clockDeltaMs),
                "t0_host_ms": .number(evidence.firstHostSeconds * 1000),
                "video_duration_ms": .number(inspection.seconds * 1000), "frame_span_ms": .number(seconds * 1000),
                "video_bytes": .number(Double(inspection.bytes)), "scheduled_duration_ms": .number(Double(timeline.endMs)),
                "writer_dropped_frames": .number(Double(video.backpressureDrops))
            ]
            quality.merge(evidence.diagnostics) { _, measured in measured }
            lastQuality = quality; lastEvents = events
            lastAttemptChallengeId = timeline.challengeId
            lastFrameCount = evidence.frameTimes.count; lastRegionCount = evidence.regionMeans.count
            payload = (data, evidence, probe, quality)
            await submit()
        } catch { if id == generation { captureFailed() } }
    }

    func submit() async {
        guard [.finishing, .failed].contains(stage), let live, let payload else { return }
        let id = generation
        stage = .uploading; errorText = nil; retryUpload = false
        live.frontalJpeg = payload.1.jpeg; live.colorEvents = events
        let next = await live.submitFace(video: payload.0, frameTimes: payload.1.frameTimes, clientQuality: payload.3,
                                        camprobe: payload.2, regionMeans: payload.1.regionMeans,
                                        onMediaAcked: { if id == self.generation { self.camera.discardRecording() } })
        guard id == generation, !Task.isCancelled else { return }
        switch next {
        case .fail(.conflict(code: "challenge_expired")), .fail(.conflict(code: "challenge_mismatch")):
            self.payload = nil; stage = .failed; retryUpload = false
            camera.stop(); camera.discardRecording(); live.abandonFaceAttempt()
            errorText = "Lượt quay đã hết hạn. Hãy căn mặt rồi thực hiện lại."
        case .fail(let error): apiFailed(error, canRetryUpload: error == .network)
        case .to(let route):
            self.payload = nil
            camera.discardRecording()
            stage = route == .voice ? .awaitingVoice : .completed
            if route != .voice { camera.stop() }
            destination = route
        }
    }

    private func apiFailed(_ error: ApiError, canRetryUpload: Bool) {
        stage = .failed; retryUpload = canRetryUpload
        camera.stop()
        if error == .network { errorText = "Không kết nối được. Kiểm tra kết nối mạng rồi thử lại." }
        else { errorText = error == .unauthorized || error == .expired ? "Phiên đã hết hạn. Hãy bắt đầu lại." : "Tạm thời chưa thể xác minh. Vui lòng thử lại sau." }
        // Expired/unknown failures never become an automatic recapture or success.
        if error != .network {
            payload = nil; camera.discardRecording(); live?.abandonFaceAttempt()
            destination = FlowRules.errorRoute(error)
        }
    }

    private func captureFailed() {
        generation += 1
        // Leave .recording BEFORE camera.stop() can synchronously publish errors.
        stage = .failed
        invalidateDisplay()
        camera.stop(); camera.discardRecording()
        payload = nil; retryUpload = false
        live?.abandonFaceAttempt()
        errorText = "Video bị gián đoạn hoặc chưa thu đủ dữ liệu. Hãy căn mặt rồi thực hiện lại."
    }

    func interrupt(route: Route = .interrupted) {
        guard stage.restartsOnInterruption else { return }
        cancel()
        stage = .interrupted
        errorText = "Xác minh bị gián đoạn. Hãy quay lại chuẩn bị."
        destination = route
    }

    func cancel() {
        generation += 1
        stage = .intro
        invalidateDisplay()
        camera.stop(); camera.discardRecording()
        payload = nil; destination = nil; retryUpload = false
        live?.abandonFaceAttempt()
    }

    func leaveFaceScreen(_ id: UUID? = nil) {
        guard id == screenID else { return }
        guard destination == nil else { return } // Teardown already handled before navigation.
        if stage != .awaitingVoice && stage != .completed { cancel() }
    }

    private func invalidateDisplay() {
        displayLink?.invalidate(); displayLink = nil
        if let oldBrightness { UIScreen.main.brightness = oldBrightness; self.oldBrightness = nil }
        if let oldIdleDisabled { UIApplication.shared.isIdleTimerDisabled = oldIdleDisabled; self.oldIdleDisabled = nil }
    }
}
