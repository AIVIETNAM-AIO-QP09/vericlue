import SwiftUI
import UIKit

struct CompletionFeedbackGate {
    private var lastEvent: String?
    mutating func consume(completed: Bool, event: String) -> Bool {
        guard completed else { lastEvent = nil; return false }
        guard lastEvent != event else { return false }
        lastEvent = event
        return true
    }
}

private struct CompletionFeedbackModifier: ViewModifier {
    let completed: Bool
    let event: String
    @State private var gate = CompletionFeedbackGate()

    func body(content: Content) -> some View {
        content
            .onAppear { emit() }
            .onChange(of: completed) { _ in emit() }
            .onChange(of: event) { _ in emit() }
    }

    private func emit() {
        guard gate.consume(completed: completed, event: event) else { return }
        // System feedback only, no custom waveform/timer or capture-clock dependency.
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
}

extension View {
    func completionFeedback(completed: Bool, event: String) -> some View {
        modifier(CompletionFeedbackModifier(completed: completed, event: event))
    }
}
