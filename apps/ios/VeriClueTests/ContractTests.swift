import Foundation
import Testing
@testable import VeriClue

@MainActor
struct ContractTests {
    @Test func everyBundledSessionExampleDecodesAndRoundTrips() throws {
        let bundle = Bundle(for: ContractFixtureBundle.self)
        let files = try #require(bundle.urls(forResourcesWithExtension: "json", subdirectory: nil))
            .filter { $0.lastPathComponent.hasPrefix("session.") && $0.lastPathComponent != "session.schema.json" }
        let expected = Set([
            "session.CreateSessionRequest.json", "session.CreateSessionResponse.json", "session.CreateSessionResponse.dynamic.json",
            "session.ErrorResponse.401.json", "session.ErrorResponse.409.json", "session.FinalizeRequest.json",
            "session.FinalizeResponse.pass.json", "session.FinalizeResponse.reauth.json", "session.FinalizeResponse.retry.json",
            "session.FinalizeResponse.review.json", "session.FinalizeResponse.voice_challenge.json", "session.Signals.json",
            "session.StepAck.json", "session.StepAck.signals.json", "session.VoiceResponse.pass.json", "session.VoiceResponse.reauth.json",
            "session.VoiceResponse.review.json", "session.VoiceResponse.voice_challenge.json"
        ])
        #expect(Set(files.map(\.lastPathComponent)) == expected)
        for file in files {
            let data = try Data(contentsOf: file)
            let type = file.lastPathComponent.split(separator: ".")[1]
            switch type {
            case "CreateSessionRequest": try roundTrip(CreateSessionRequest.self, data)
            case "CreateSessionResponse": try roundTrip(CreateSessionResponse.self, data)
            case "ErrorResponse": try roundTrip(ErrorResponse.self, data)
            case "FinalizeRequest": try roundTrip(FinalizeRequest.self, data)
            case "FinalizeResponse": try roundTrip(FinalizeResponse.self, data)
            case "Signals": try roundTrip(Signals.self, data)
            case "StepAck": try roundTrip(StepAck.self, data)
            case "VoiceResponse": try roundTrip(VoiceResponse.self, data)
            default: Issue.record("Unmapped contract fixture: \(file.lastPathComponent)")
            }
        }
        let dynamic = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        #expect(dynamic.challenge.dynamic?.voiceChallengeId.hasPrefix("vc_") == true)
        #expect(dynamic.challenge.dynamic?.gazePoints.count == 8)
    }

    @Test func schemaRequiredFieldsAreReallyRequiredAndOptionalsMayBeOmitted() throws {
        let data = try Fixtures.data("session.schema")
        let schema = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let defs = try #require(schema["$defs"] as? [String: [String: Any]])
        let legacy = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session())
        let dynamic = try #require(SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true)).challenge.dynamic)
        try checkModel("CreateSessionResponse", legacy, defs)
        try checkModel("Challenge", legacy.challenge, defs)
        try checkModel("ColorStep", legacy.challenge.colorSequence[0], defs)
        try checkModel("DynamicChallenge", dynamic, defs)
        try checkModel("GazePoint", dynamic.gazePoints[0], defs)
        try checkModel("CreateSessionRequest", CreateSessionRequest(purpose: "onboarding", nonce: "ios_fixture_nonce_12345"), defs)
        try checkModel("ChallengeResponse", ChallengeResponse(token: "new", expiresAt: "2026-10-24T10:00:00Z", challenge: legacy.challenge), defs)
        try checkModel("OtpRequest", OtpRequest(phone: "0912345678"), defs)
        try checkModel("OtpVerifyRequest", OtpVerifyRequest(code: "123456"), defs)
        try checkModel("OtpSent", OtpSent(expiresAt: "2026-10-24T10:00:00Z", attemptsLeft: 5, simulatedSms: "sample"), defs)
        try checkModel("OtpVerifyResponse", OtpVerifyResponse(status: "pass", attemptsLeft: 5), defs)
        try checkModel("IdCardFields", IdCardFields(fullName: "Nguyễn Văn An", idNumber: "001099012345", dateOfBirth: "1995-01-01", sex: "Nam", address: "Hà Nội", issuedOn: "2021-06-15"), defs)
        try checkModel("IdCardResponse", IdCardResponse(status: "ok", fields: IdCardFields()), defs)
        try checkModel("IdCardConfirmResponse", IdCardConfirmResponse(received: true), defs)
        try checkModel("StepAck", StepAck(step: "media", received: true), defs)
        try checkModel("FinalizeRequest", FinalizeRequest(challengeId: "ch_1"), defs)
        try checkModel("FinalizeResponse", FinalizeResponse(status: "retry", retryHint: "MORE_LIGHT", attemptsLeft: 1, challenge: legacy.challenge), defs)
        try checkModel("VoiceResponse", VoiceResponse(status: "voice_challenge", voicePrompt: "Câu mới", attemptsLeft: 1, voiceChallengeId: "vc_1"), defs)
        try checkModel("ErrorResponse", ErrorResponse(errorCode: "session_closed", message: "diagnostic"), defs)
        try checkModel("Signals", Signals(colorEvents: [], frameTimes: []), defs)
    }

    @Test func signalsNestedObjectsMatchSchemaWithoutDroppingDiagnosticTypes() throws {
        let frame = FrameTime(captureTime: nil, presentedFrames: 1, mediaTime: 0.5)
        let camprobe = CamProbe(apiTamperFlags: [], constraintProbes: [["ok": .bool(true)]], deviceLabel: "iPhone", trackSettings: ["width": .number(720)], trackCapabilities: ["focus": .array([.string("auto")])], duplicateFrameRatio: 0.01)
        let signals = Signals(colorEvents: [ColorEvent(index: 0, rgb: "#80e09e", paintedAt: 100)], frameTimes: [frame], clientQuality: ["fps": .number(30), "has_video": .bool(true)], camprobe: camprobe, regionMeans: [["at_ms": .number(100), "skin": .array([.number(1), .number(2), .number(3)])]], challengeId: "ch_1")
        try roundTrip(Signals.self, SessionJSON.encoder().encode(signals))
        let object = try #require(JSONSerialization.jsonObject(with: SessionJSON.encoder().encode(signals)) as? [String: Any])
        let frames = try #require(object["frame_times"] as? [[String: Any]])
        #expect(frames[0]["presented_frames"] as? Int == 1)
        let probe = try #require(object["camprobe"] as? [String: Any])
        #expect(Set(probe.keys) == ["api_tamper_flags", "constraint_probes", "device_label", "track_settings", "track_capabilities", "duplicate_frame_ratio"])
        #expect(try SessionJSON.decoder().decode(FrameTime.self, from: Data("{}".utf8)) == FrameTime())
    }

    private func roundTrip<T: Codable & Equatable>(_ type: T.Type, _ data: Data) throws {
        let model = try SessionJSON.decoder().decode(type, from: data)
        #expect(try SessionJSON.decoder().decode(type, from: SessionJSON.encoder().encode(model)) == model)
    }

    private func checkModel<T: Codable>(_ name: String, _ model: T, _ defs: [String: [String: Any]]) throws {
        let definition = try #require(defs[name])
        let properties = try #require(definition["properties"] as? [String: Any])
        let required = Set(definition["required"] as? [String] ?? [])
        let encoded = try #require(JSONSerialization.jsonObject(with: SessionJSON.encoder().encode(model)) as? [String: Any])
        #expect(Set(encoded.keys).isSubset(of: Set(properties.keys)))
        #expect(required.isSubset(of: Set(encoded.keys)))
        let minimal = encoded.filter { required.contains($0.key) }
        _ = try SessionJSON.decoder().decode(T.self, from: JSONSerialization.data(withJSONObject: minimal))
        for key in required {
            var missing = minimal
            missing.removeValue(forKey: key)
            #expect(throws: DecodingError.self, "\(name) must require \(key)") {
                _ = try SessionJSON.decoder().decode(T.self, from: JSONSerialization.data(withJSONObject: missing))
            }
        }
    }
}
