#if DEBUG
import Foundation
import SwiftUI

// Separate Keychain namespace; synthetic bytes never enter the live receipt store.
struct ReceiptKeychainCheckpoint: View {
    @State private var message = "Chưa kiểm tra. Dữ liệu tổng hợp, không phải tài khoản thật."
    @State private var busy = false
    private static let backend = KeychainReceiptDataStore(service: "vn.vericlue.debug.receipt-check")
    private static let store = AccountStore(backend: backend)

    private static func sample(expiresAt: Date) -> AccountReceipt {
        AccountReceipt(accountId: "acct_" + String(repeating: "e", count: 32),
            deviceId: "dev_" + String(repeating: "f", count: 32),
            expiresAt: ISO8601DateFormatter().string(from: expiresAt))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Keychain receipt · Kiểm tra DEBUG").font(VcType.label)
            Text("Kho kiểm tra riêng. Không tạo tài khoản, không thay device proof.")
                .font(VcType.caption)
            Button("1. Ghi dữ liệu kiểm tra") {
                perform {
                    try await Self.store.save(Self.sample(expiresAt: Date().addingTimeInterval(86400)))
                    return "Đã ghi item kiểm tra. Đóng hẳn app, mở lại rồi bấm 2."
                }
            }
            Button("2. Đọc lại sau khi mở app") {
                perform {
                    let receipt = try await Self.store.load()
                    guard let receipt else { return "Kho kiểm tra rỗng (hoặc item đã hết hạn)." }
                    guard receipt.accountId == "acct_" + String(repeating: "e", count: 32),
                          receipt.deviceId == "dev_" + String(repeating: "f", count: 32) else {
                        return "KHÔNG ĐẠT: dữ liệu kiểm tra không khớp."
                    }
                    return "ĐẠT: đọc đúng dữ liệu kiểm tra còn hạn từ Keychain."
                }
            }
            Button("3. Xóa item kiểm tra") {
                perform {
                    try await Self.store.clear()
                    guard try await Self.store.load() == nil else { return "KHÔNG ĐẠT: item chưa được xóa." }
                    return "ĐẠT: đã xóa, đọc lại trả rỗng. Không xóa receipt của luồng thật."
                }
            }
            Button("4. Kiểm dữ liệu hỏng / hết hạn") {
                perform {
                    // No await between direct backend writes and the next actor call;
                    // busy disables other probe actions. Only this probe owns its namespace.
                    try Self.backend.write(Data("{}".utf8))
                    guard try await Self.store.load() == nil, try Self.backend.read() == nil else {
                        return "KHÔNG ĐẠT: dữ liệu hỏng chưa được dọn."
                    }
                    let now = Date()
                    let receipt = Self.sample(expiresAt: now.addingTimeInterval(60))
                    try await Self.store.save(receipt, at: now)
                    guard try await Self.store.load(at: now.addingTimeInterval(120)) == nil,
                          try Self.backend.read() == nil else {
                        return "KHÔNG ĐẠT: dữ liệu hết hạn chưa được dọn."
                    }
                    return "ĐẠT: dữ liệu hỏng/hết hạn được dọn. Dùng mốc giờ truyền vào, không đổi giờ iPhone."
                }
            }
            Button("Đọc kho receipt của luồng thật (chỉ trạng thái)") {
                perform {
                    let receipt = try await AccountStore.shared.load()
                    return receipt == nil
                        ? "Kho receipt thật rỗng. Đây là trạng thái dự kiến khi backend chỉ chạy mock."
                        : "Có receipt thật còn hạn trong kho. Chưa xác minh lại với server; không coi là đăng nhập thành công."
                }
            }
            Text(message).font(VcType.caption).accessibilityIdentifier("debug-receipt-keychain-result")
        }
        .font(VcType.label)
        .disabled(busy)
    }

    private func perform(_ action: @escaping @MainActor () async throws -> String) {
        guard !busy else { return }
        busy = true
        Task { @MainActor in
            defer { busy = false }
            do { message = try await action() }
            catch { message = "Không kiểm tra được Keychain. Mở khóa iPhone rồi thử lại; không kết luận đạt." }
        }
    }
}
#endif
