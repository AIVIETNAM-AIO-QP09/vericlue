import CryptoKit
import Foundation
import Security

enum KeyAliases {
    nonisolated static func valid(_ value: String) -> Bool {
        value.range(of: "\\Avericlue\\.media\\.[A-Za-z0-9._-]{1,100}\\z", options: .regularExpression) != nil
    }
    nonisolated static func fresh() -> String { "vericlue.media." + UUID().uuidString }
}

// One actor serializes key creation across signer instances. No private-key export API.
actor DeviceKeyStore: AccountKeys {
    nonisolated static let shared = DeviceKeyStore()

    private func query(_ alias: String) throws -> [String: Any] {
        guard KeyAliases.valid(alias) else { throw ProofError.invalidContext }
        return [kSecClass as String: kSecClassKey,
                kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
                kSecAttrKeyClass as String: kSecAttrKeyClassPrivate,
                kSecAttrApplicationTag as String: Data(alias.utf8)]
    }

    private func find(_ alias: String) throws -> SecKey? {
        var attributes = try query(alias)
        attributes[kSecReturnRef as String] = true
        attributes[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(attributes as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let item else { throw ProofError.keychain(status) }
        guard CFGetTypeID(item) == SecKeyGetTypeID() else { throw ProofError.unavailableKey }
        return (item as! SecKey)
    }

    func exists(_ alias: String) throws -> Bool { try find(alias) != nil }

    func open(_ alias: String, create: Bool) throws -> any MediaSigner {
        _ = try key(alias, create: create)
        return try KeychainMediaSigner(alias: alias, createIfMissing: false, store: self)
    }

    private func key(_ alias: String, create: Bool) throws -> SecKey {
        if let value = try find(alias) { return value }
        guard create else { throw ProofError.unavailableKey }
        var attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String: true,
                kSecAttrApplicationTag as String: Data(alias.utf8),
                kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
                kSecAttrIsExtractable as String: false
            ]
        ]
        #if !targetEnvironment(simulator)
        // Never silently create an exportable replacement if hardware key creation fails.
        guard SecureEnclave.isAvailable else { throw ProofError.unavailableKey }
        attributes[kSecAttrTokenID as String] = kSecAttrTokenIDSecureEnclave
        var accessError: Unmanaged<CFError>?
        guard let access = SecAccessControlCreateWithFlags(kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly, .privateKeyUsage, &accessError) else {
            _ = accessError?.takeRetainedValue()
            throw ProofError.signing
        }
        attributes[kSecPrivateKeyAttrs as String] = [
            kSecAttrIsPermanent as String: true,
            kSecAttrApplicationTag as String: Data(alias.utf8),
            kSecAttrAccessControl as String: access
        ]
        #endif
        var error: Unmanaged<CFError>?
        guard let value = SecKeyCreateRandomKey(attributes as CFDictionary, &error) else {
            _ = error?.takeRetainedValue()
            throw ProofError.signing
        }
        return value
    }

    func publicKeySPKI(alias: String, create: Bool) throws -> String {
        let privateKey = try key(alias, create: create)
        var error: Unmanaged<CFError>?
        guard let publicKey = SecKeyCopyPublicKey(privateKey),
              let bytes = SecKeyCopyExternalRepresentation(publicKey, &error) as Data?,
              bytes.count == 65, bytes.first == 4 else {
            _ = error?.takeRetainedValue()
            throw ProofError.signing
        }
        // DER SubjectPublicKeyInfo: id-ecPublicKey + prime256v1 + X9.63 point.
        let header = Data([0x30,0x59,0x30,0x13,0x06,0x07,0x2a,0x86,0x48,0xce,0x3d,0x02,0x01,
                           0x06,0x08,0x2a,0x86,0x48,0xce,0x3d,0x03,0x01,0x07,0x03,0x42,0x00])
        return (header + bytes).base64EncodedString()
    }

    func sign(alias: String, create: Bool, message: Data) throws -> String {
        let value = try key(alias, create: create)
        let algorithm = SecKeyAlgorithm.ecdsaSignatureMessageX962SHA256
        var error: Unmanaged<CFError>?
        guard SecKeyIsAlgorithmSupported(value, .sign, algorithm),
              let result = SecKeyCreateSignature(value, algorithm, message as CFData, &error) as Data?
        else {
            _ = error?.takeRetainedValue()
            throw ProofError.signing
        }
        return result.base64EncodedString()
    }

    func delete(_ alias: String) throws {
        let status = SecItemDelete(try query(alias) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw ProofError.keychain(status) }
    }

    func delete(_ alias: String, lease: OperationLease) throws {
        try lease.perform { try delete(alias) }
    }
}

struct KeychainMediaSigner: MediaSigner {
    let alias: String
    let createIfMissing: Bool
    let store: DeviceKeyStore

    nonisolated init(alias: String, createIfMissing: Bool, store: DeviceKeyStore = .shared) throws {
        guard KeyAliases.valid(alias) else { throw ProofError.invalidContext }
        self.alias = alias; self.createIfMissing = createIfMissing; self.store = store
    }
    func publicKeySPKI() async throws -> String { try await store.publicKeySPKI(alias: alias, create: createIfMissing) }
    func sign(_ message: Data) async throws -> String { try await store.sign(alias: alias, create: createIfMissing, message: message) }
}
