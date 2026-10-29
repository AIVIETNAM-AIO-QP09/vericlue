import Foundation

nonisolated struct StoredAccount: Codable, Equatable, Sendable {
    let receipt: AccountReceipt
    let keyAlias: String
    nonisolated func isUsable(at now: Date) -> Bool { receipt.isUsable(at: now) && KeyAliases.valid(keyAlias) }
}

actor AccountBindingStore {
    static let shared = AccountBindingStore()
    private let backend: any ReceiptDataStore
    init(backend: any ReceiptDataStore = KeychainReceiptDataStore(service: "vn.vericlue.account-binding.v2")) {
        self.backend = backend
    }
    func load(at now: Date = Date()) throws -> StoredAccount? {
        try Task.checkCancellation()
        guard let data = try backend.read() else { return nil }
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let value = try? decoder.decode(StoredAccount.self, from: data), value.isUsable(at: now) else {
            try backend.delete() // Receipt-only bytes cannot establish an enrolled alias.
            return nil
        }
        return value
    }
    func save(_ value: StoredAccount, replacing previous: StoredAccount? = nil,
              lease: OperationLease, at now: Date = Date()) throws {
        try lease.perform {
            guard value.isUsable(at: now) else { throw AccountStoreError.invalidReceipt }
            if let previous {
                guard try load(at: now) == previous else { throw AccountStoreError.invalidReceipt }
            }
            let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase
            // Single atomic Keychain update for receipt+alias; no delete-before-write.
            try backend.write(encoder.encode(value))
        }
    }
    func clear() throws { try Task.checkCancellation(); try backend.delete() }
}
