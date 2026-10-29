import Foundation

// Never hold this lock across an await. Revokes durable writes by abandoned work.
final class OperationLease: @unchecked Sendable {
    nonisolated private let lock = NSLock()
    nonisolated(unsafe) private var valid = true
    nonisolated func invalidate() { lock.lock(); valid = false; lock.unlock() }
    nonisolated func perform<T>(_ work: () throws -> T) throws -> T {
        lock.lock(); defer { lock.unlock() }
        guard valid, !Task.isCancelled else { throw CancellationError() }
        return try work()
    }
}
