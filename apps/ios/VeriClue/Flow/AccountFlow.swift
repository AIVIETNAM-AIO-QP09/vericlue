import Foundation

nonisolated protocol AccountKeys: Sendable {
    nonisolated func exists(_ alias: String) async throws -> Bool
    nonisolated func open(_ alias: String, create: Bool) async throws -> any MediaSigner
    nonisolated func delete(_ alias: String, lease: OperationLease) async throws
}

struct AccountEntry: Sendable {
    let purpose: Purpose
    let receipt: AccountReceipt?
    let keyAlias: String?
    let signer: (any MediaSigner)?
    let route: Route
    var hint: String? = nil
    var previous: StoredAccount? = nil
}

enum AccountPersistenceOutcome: Equatable { case saved, unavailable, contextMismatch, storage, oldKeyCleanup }

@MainActor
final class AccountFlow {
    let store: AccountBindingStore
    let keys: any AccountKeys
    init(store: AccountBindingStore = .shared, keys: any AccountKeys = DeviceKeyStore.shared) {
        self.store = store; self.keys = keys
    }
    func begin(_ requested: Purpose, signingEnabled: Bool) async throws -> AccountEntry {
        let saved = try await store.load()
        try Task.checkCancellation()
        if requested == .reauth, signingEnabled, let saved {
            guard try await keys.exists(saved.keyAlias) else {
                return AccountEntry(purpose: requested, receipt: saved.receipt, keyAlias: saved.keyAlias,
                    signer: nil, route: .recoveryRequired)
            }
            let signer = try await keys.open(saved.keyAlias, create: false)
            return AccountEntry(purpose: requested, receipt: saved.receipt, keyAlias: saved.keyAlias,
                signer: signer, route: .phone)
        }
        let fallback = requested != .onboarding && (!signingEnabled || saved == nil)
        let purpose: Purpose = fallback ? .onboarding : requested
        let alias = signingEnabled ? KeyAliases.fresh() : nil
        guard purpose != .recovery || alias != saved?.keyAlias else { throw ProofError.invalidContext }
        let signer: (any MediaSigner)?
        if let alias { signer = try await keys.open(alias, create: true) } else { signer = nil }
        try Task.checkCancellation()
        return AccountEntry(purpose: purpose, receipt: purpose == .recovery ? saved?.receipt : nil,
            keyAlias: alias, signer: signer, route: purpose == .onboarding ? .terms : .phone,
            hint: fallback ? "Vui lòng đăng ký để tiếp tục." : nil,
            previous: purpose == .recovery ? saved : nil)
    }
    // Only after confirmed server pass, before returning the success route.
    func persist(_ receipt: AccountReceipt?, entry: AccountEntry, lease: OperationLease) async throws -> AccountPersistenceOutcome {
        guard entry.purpose != .reauth, let alias = entry.keyAlias,
              let receipt, receipt.isUsable() else { return .unavailable }
        if entry.purpose == .recovery {
            guard let previous = entry.previous, receipt.accountId == previous.receipt.accountId,
                  receipt.deviceId != previous.receipt.deviceId, alias != previous.keyAlias else { return .contextMismatch }
        }
        do {
            try await store.save(StoredAccount(receipt: receipt, keyAlias: alias), replacing: entry.previous, lease: lease)
        } catch is CancellationError { throw CancellationError() }
        catch { return .storage }
        if let previous = entry.previous, previous.keyAlias != alias {
            do { try await keys.delete(previous.keyAlias, lease: lease) }
            catch is CancellationError { throw CancellationError() }
            catch { return .oldKeyCleanup } // Durable new binding is not rolled back.
        }
        return .saved
    }
}

enum SigningConfiguration {
    nonisolated static var enabled: Bool {
        guard let raw = Bundle.main.object(forInfoDictionaryKey: "SIGNED_MEDIA") as? String else { return false }
        return ["yes", "true", "1"].contains(raw.lowercased())
    }
}
