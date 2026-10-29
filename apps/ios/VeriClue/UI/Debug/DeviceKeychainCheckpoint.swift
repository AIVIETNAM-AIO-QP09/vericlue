#if DEBUG
import CryptoKit
import Foundation
import SwiftUI

nonisolated struct DeviceKeyProbeRecord: Codable {
    let alias: String
    var publicKey: String?
}

enum DeviceKeyProbeError: Error { case busy, missing, incomplete, wrongOwner, mismatch }

// No receipt/account/network. Only aliases created by this probe may be deleted.
@MainActor
final class DeviceKeyProbe {
    static let shared = DeviceKeyProbe()
    nonisolated static let prefix = "vericlue.media.debug-check-"
    private let backend: any ReceiptDataStore
    private let keys: any AccountKeys
    private var busy = false

    init(backend: any ReceiptDataStore = KeychainReceiptDataStore(service: "vn.vericlue.debug.device-key"),
         keys: any AccountKeys = DeviceKeyStore.shared) {
        self.backend = backend; self.keys = keys
    }

    nonisolated static func owns(_ alias: String) -> Bool {
        guard alias.hasPrefix(prefix), KeyAliases.valid(alias) else { return false }
        return UUID(uuidString: String(alias.dropFirst(prefix.count))) != nil
    }

    private func record() throws -> DeviceKeyProbeRecord? {
        guard let data = try backend.read() else { return nil }
        let value = try JSONDecoder().decode(DeviceKeyProbeRecord.self, from: data)
        guard Self.owns(value.alias) else { throw DeviceKeyProbeError.wrongOwner }
        return value
    }

    func create() async throws {
        guard !busy else { throw DeviceKeyProbeError.busy }
        busy = true; defer { busy = false }
        guard try record() == nil else { throw DeviceKeyProbeError.incomplete }
        var value = DeviceKeyProbeRecord(alias: Self.prefix + UUID().uuidString)
        // Persist ownership first: interruption cannot leave a key with no cleanup handle.
        try backend.write(JSONEncoder().encode(value))
        do {
            let signer = try await keys.open(value.alias, create: true)
            value.publicKey = try await signer.publicKeySPKI()
            try backend.write(JSONEncoder().encode(value))
        } catch {
            do {
                try await keys.delete(value.alias, lease: OperationLease())
                try backend.delete()
            } catch { /* Keep ownership metadata if cleanup failed, so the user can retry. */ }
            throw error
        }
    }

    func reopenAndVerify() async throws {
        guard !busy else { throw DeviceKeyProbeError.busy }
        busy = true; defer { busy = false }
        guard let value = try record() else { throw DeviceKeyProbeError.missing }
        guard let expected = value.publicKey else { throw DeviceKeyProbeError.incomplete }
        let signer = try await keys.open(value.alias, create: false)
        let spki = try await signer.publicKeySPKI()
        guard spki == expected, let publicData = Data(base64Encoded: spki) else { throw DeviceKeyProbeError.mismatch }
        let message = Data("VeriClue isolated device key checkpoint v1".utf8)
        let signature = try await signer.sign(message)
        guard let bytes = Data(base64Encoded: signature) else { throw DeviceKeyProbeError.mismatch }
        let key = try P256.Signing.PublicKey(derRepresentation: publicData)
        let proof = try P256.Signing.ECDSASignature(derRepresentation: bytes)
        guard key.isValidSignature(proof, for: message),
              !key.isValidSignature(proof, for: message + Data([0])) else { throw DeviceKeyProbeError.mismatch }
    }

    func removeKeyButKeepRecord() async throws {
        guard !busy else { throw DeviceKeyProbeError.busy }
        busy = true; defer { busy = false }
        guard let value = try record() else { throw DeviceKeyProbeError.missing }
        try await keys.delete(value.alias, lease: OperationLease())
        guard try await keys.exists(value.alias) == false else { throw DeviceKeyProbeError.mismatch }
        do {
            _ = try await keys.open(value.alias, create: false)
            throw DeviceKeyProbeError.mismatch
        } catch ProofError.unavailableKey { /* Expected: never generate a replacement. */ }
    }

    func clear() async throws {
        guard !busy else { throw DeviceKeyProbeError.busy }
        busy = true; defer { busy = false }
        if let value = try record() { try await keys.delete(value.alias, lease: OperationLease()) }
        try backend.delete()
    }
}

struct DeviceKeychainCheckpoint: View {
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var message = "Chưa kiểm tra. Không đụng khóa hoặc receipt tài khoản."

    var body: some View {
        NavigationStack {
            VcScreen {
                VcTitleBlock(title: "Khóa ký · kiểm tra riêng", bodyText: "Chỉ dùng khóa thử. Không tạo tài khoản, không gọi server.")
                #if targetEnvironment(simulator)
                Text("Simulator dùng khóa phát triển; không phải nghiệm thu Secure Enclave.").font(VcType.caption)
                #else
                Text("Máy thật dùng cùng DeviceKeyStore của app; không tự chuyển sang khóa phần mềm.").font(VcType.caption)
                #endif
                Button("1. Tạo khóa thử") {
                    perform { try await DeviceKeyProbe.shared.create(); return "Đã tạo. Đóng hẳn app rồi mở lại, vào đây bấm 2." }
                }
                Button("2. Mở lại và ký kiểm tra") {
                    perform {
                        try await DeviceKeyProbe.shared.reopenAndVerify()
                        return "ĐẠT: public key không đổi, ký hợp lệ; dữ liệu bị sửa không qua. Chưa phải L0 với server."
                    }
                }
                Button("3. Xóa khóa thử, giữ metadata") {
                    perform {
                        try await DeviceKeyProbe.shared.removeKeyButKeepRecord()
                        return "ĐẠT: mất khóa thử; open(create:false) bị từ chối, không tạo khóa thay. Bấm 4 để dọn metadata."
                    }
                }
                Button("4. Dọn khóa và metadata thử") {
                    perform { try await DeviceKeyProbe.shared.clear(); return "Đã dọn kho thử. Không xóa dữ liệu tài khoản." }
                }
                Text(message).font(VcType.caption).accessibilityIdentifier("debug-device-key-result")
            }
            .font(VcType.label)
            .disabled(busy)
            .navigationTitle("Khóa thử riêng")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Đóng") { dismiss() }.disabled(busy) } }
        }
    }

    private func perform(_ operation: @escaping @MainActor () async throws -> String) {
        guard !busy else { return }
        busy = true
        Task {
            defer { busy = false }
            do { message = try await operation() }
            catch ProofError.unavailableKey { message = "Khóa thử không còn hoặc không dùng được. Không kết luận đạt; dùng bước 4 trước khi tạo lại." }
            catch DeviceKeyProbeError.incomplete { message = "Kho thử đã có dữ liệu hoặc chưa tạo xong. Thử bước 2, hoặc dọn bằng bước 4." }
            catch { message = "Không kiểm tra được. Mở khóa iPhone và thử lại; không kết luận đạt." }
        }
    }
}
#endif
