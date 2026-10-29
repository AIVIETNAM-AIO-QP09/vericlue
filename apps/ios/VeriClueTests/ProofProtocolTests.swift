import CryptoKit
import Foundation
import Testing
@testable import VeriClue

@MainActor
struct ProofProtocolTests {
    @Test func sha256HexPreservesZeroPaddingAndLowercase() {
        #expect(MediaProof.sha256(Data()) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        #expect(MediaProof.sha256(Data("abc".utf8)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    }

    private func session() -> CreateSessionResponse {
        CreateSessionResponse(sessionId: "ses_golden", token: "synthetic-test-token", expiresAt: "2099-01-01T00:00:00Z",
            challenge: Challenge(challengeId: "ch_golden", colorSequence: [], mediaNonce: String(repeating: "0", count: 64)),
            purpose: "onboarding", nonce: "synthetic_nonce_1234")
    }

    // Public test vector from upstream 54acaad packages/contracts/test-vectors/media-proof-v1.json.
    // It contains no private key or user media. Hashing input is the literal ASCII "abc".
    @Test func manifestMatchesSharedGoldenHashAndECDSASignature() throws {
        let s = session()
        let digest = try MediaProof.digest(name: "face.jpg", bytes: Data("abc".utf8))
        let data = try MediaProof.manifest(session: s, challenge: s.challenge, stage: "face",
            attemptID: "ch_golden", files: ["image": digest])
        #expect(MediaProof.sha256(data) == "751bb8d1f32630fffac5aecfa1759c99a72f0c3229cd1ed4a0e9ac9696b755bc")
        let keyData = try #require(Data(base64Encoded: "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEmX2VIsZRcdz/VFrCWqN4BXXHM4DWIcQdmBzAXPjsVLG0iOQnLQM6mi7gEpx4+3+okeL5VUjnnKuE9vKe6zXwbw=="))
        let signatureData = try #require(Data(base64Encoded: "MEYCIQDwX4OnXteYfDGFH8mIIisYCJIoNg/xjyyFt6eFip/CngIhAJthb1mr6KGfQaouKfo0DvShUKq3sGIOJ3Nk62nAAmCa"))
        let key = try P256.Signing.PublicKey(derRepresentation: keyData)
        let signature = try P256.Signing.ECDSASignature(derRepresentation: signatureData)
        #expect(key.isValidSignature(signature, for: data))
        #expect(!key.isValidSignature(signature, for: data + Data([0])))
    }

    @Test func manifestBindsBytesStageChallengeSuffixAndOffset() throws {
        let s = session()
        let audio = try MediaProof.digest(name: "voice.WAV", bytes: Data([1,2,3]))
        let video = try MediaProof.digest(name: "voice.mp4", bytes: Data([4,5,6]))
        let data = try MediaProof.manifest(session: s, challenge: s.challenge, stage: "voice",
            attemptID: "vc_test", files: ["audio": audio, "video": video], audioOffsetMs: 114)
        let changed = try MediaProof.manifest(session: s, challenge: s.challenge, stage: "voice",
            attemptID: "vc_test", files: ["audio": audio, "video": video], audioOffsetMs: 115)
        #expect(data != changed && audio.suffix == ".wav")
        #expect(throws: ProofError.self) {
            try MediaProof.manifest(session: s, challenge: s.challenge, stage: "face", attemptID: "ch_golden", files: ["audio": audio])
        }
        #expect(throws: ProofError.self) {
            try MediaProof.manifest(session: s, challenge: s.challenge, stage: "voice", attemptID: "vc_test", files: ["audio": audio], audioOffsetMs: 1)
        }
        #expect(throws: ProofError.self) { try MediaProof.digest(name: "empty.jpg", bytes: Data()) }
        var unsigned = s.challenge; unsigned.mediaNonce = nil
        #expect(throws: ProofError.self) {
            try MediaProof.manifest(session: s, challenge: unsigned, stage: "face", attemptID: "ch_golden", files: ["image": video])
        }
    }

    private func deviceContext() throws -> (CreateSessionResponse, AccountReceipt, Data) {
        let account = AccountReceipt(accountId: "acct_" + String(repeating: "a", count: 32),
            deviceId: "dev_" + String(repeating: "b", count: 32), expiresAt: "2099-01-01T00:00:00Z")
        var s = session(); s.purpose = "reauth"
        let object: [String: Any] = ["version": "vericlue-device-auth-v1", "session_id": s.sessionId,
            "account_id": account.accountId, "device_id": account.deviceId, "purpose": "reauth",
            "nonce": s.nonce!, "server_nonce": String(repeating: "c", count: 64), "expires_at_ms": 1893456000000 as Int64]
        let bytes = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        s.deviceChallenge = DeviceChallenge(message: bytes.base64EncodedString(), expiresAt: "2030-01-01T00:00:00Z")
        return (s, account, bytes)
    }

    @Test func deviceProofChecksContextAndSignsExactServerBytes() throws {
        let (s, account, bytes) = try deviceContext()
        let now = Date(timeIntervalSince1970: 1800000000)
        #expect(try DeviceProof.payload(session: s, account: account, nonce: s.nonce!, now: now) == bytes)
        #expect(throws: ProofError.self) { try DeviceProof.payload(session: s, account: account, nonce: "wrong", now: now) }
        #expect(throws: ProofError.self) {
            try DeviceProof.payload(session: s, account: account, nonce: s.nonce!, now: Date(timeIntervalSince1970: 1893456000))
        }
        let other = CreateSessionResponse(sessionId: "ses_other", token: s.token, expiresAt: s.expiresAt,
            challenge: s.challenge, purpose: s.purpose, nonce: s.nonce, deviceChallenge: s.deviceChallenge)
        #expect(throws: ProofError.self) { try DeviceProof.payload(session: other, account: account, nonce: s.nonce!, now: now) }
        var malformed = s
        malformed.deviceChallenge = DeviceChallenge(message: s.deviceChallenge!.message + "\n", expiresAt: "2030-01-01T00:00:00Z")
        #expect(throws: ProofError.self) { try DeviceProof.payload(session: malformed, account: account, nonce: s.nonce!, now: now) }
    }

    @Test func missingEnrollmentKeyAliasesCannotBeInventedOrBroadened() {
        #expect(KeyAliases.valid(KeyAliases.fresh()))
        for alias in ["", "vericlue.media.", "../key", "vericlue.media.a/b", "other.key"] {
            #expect(!KeyAliases.valid(alias))
        }
    }

    @Test func optionalProofFieldsDoNotBreakOldModels() throws {
        let old = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session())
        #expect(old.challenge.mediaNonce == nil && old.deviceChallenge == nil)
        let request = CreateSessionRequest(purpose: "reauth", nonce: "synthetic_nonce", accountId: "synthetic_account", deviceId: "synthetic_device")
        let encoded = try SessionJSON.encoder().encode(request)
        let object = try #require(try JSONSerialization.jsonObject(with: encoded) as? [String: Any])
        #expect(object["account_id"] as? String == "synthetic_account" && object["device_id"] as? String == "synthetic_device")
        #expect(object["device_public_key_spki"] == nil)
    }

    @Test func deviceProofAndSignaturesUseExpectedHTTPParts() async throws {
        let server = MockServer(), api = server.api()
        server.enqueue("{\"received\":true}")
        #expect(try await api.proveDevice(sessionId: "ses_test", token: "synthetic", signature: "signature").get().received)
        #expect(server.captured[0].url?.path == "/v1/sessions/ses_test/device-proof")
        #expect(server.captured[0].value(forHTTPHeaderField: "Authorization") == "Bearer synthetic")
        server.enqueue(Fixtures.mediaAck)
        _ = try await api.sendMedia(sessionId: "ses_test", token: "synthetic", imageJpeg: Data([1]),
            video: nil, challengeId: "ch_test", mediaSignature: "signed-face").get()
        let body = String(decoding: server.captured[1].httpBody!, as: UTF8.self)
        #expect(body.contains("name=\"media_signature\"\r\n\r\nsigned-face"))
    }
}
