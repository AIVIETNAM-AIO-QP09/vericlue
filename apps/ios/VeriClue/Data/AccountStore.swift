import Foundation
import Security

enum AccountStoreError: Error, Equatable {
    case invalidReceipt
    case keychain(OSStatus)
}

// Only encoded AccountReceipt bytes enter this backend; never session tokens/media.
protocol ReceiptDataStore: Sendable {
    nonisolated func read() throws -> Data?
    nonisolated func write(_ data: Data) throws
    nonisolated func delete() throws
}

struct KeychainReceiptDataStore: ReceiptDataStore {
    private let service: String

    nonisolated init(service: String = "vn.vericlue.account-receipt") { self.service = service }

    nonisolated private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: "receipt.v1",
         kSecAttrSynchronizable as String: false]
    }

    nonisolated func read() throws -> Data? {
        var request = query
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var value: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &value)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw AccountStoreError.keychain(status) }
        guard let data = value as? Data else { throw AccountStoreError.invalidReceipt }
        return data
    }

    nonisolated func write(_ data: Data) throws {
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            attributes.forEach { item[$0.key] = $0.value }
            status = SecItemAdd(item as CFDictionary, nil)
            // Another store instance may have created the same item meanwhile.
            if status == errSecDuplicateItem { status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary) }
        }
        guard status == errSecSuccess else { throw AccountStoreError.keychain(status) }
    }

    nonisolated func delete() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw AccountStoreError.keychain(status) }
    }
}

// Serial actor keeps blocking Security calls off MainActor and orders save/load/clear.
// Tests inject a memory backend: no real Keychain, biometrics, or network access.
actor AccountStore {
    static let shared = AccountStore()
    private let backend: any ReceiptDataStore

    init(backend: any ReceiptDataStore = KeychainReceiptDataStore()) { self.backend = backend }

    func load(at now: Date = Date()) throws -> AccountReceipt? {
        try Task.checkCancellation()
        guard let data = try backend.read() else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let receipt = try? decoder.decode(AccountReceipt.self, from: data), receipt.isUsable(at: now) else {
            // Only malformed/expired data is removed. Locked/unavailable Keychain
            // errors propagate from read(), without deleting a valid old receipt.
            try backend.delete()
            return nil
        }
        return receipt
    }

    func save(_ receipt: AccountReceipt, at now: Date = Date()) throws {
        try Task.checkCancellation()
        guard receipt.isUsable(at: now) else { throw AccountStoreError.invalidReceipt }
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        try backend.write(encoder.encode(receipt))
    }

    func clear() throws {
        try Task.checkCancellation()
        try backend.delete()
    }
}
