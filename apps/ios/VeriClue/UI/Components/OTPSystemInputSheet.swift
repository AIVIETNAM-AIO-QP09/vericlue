import SwiftUI

// Native keyboard is required for iOS security-code AutoFill; never reads the SMS inbox.
struct OTPSystemInputSheet: View {
    @Binding var code: String
    var enabled = true
    @FocusState private var focused: Bool
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                TextField("Mã gồm 6 số", text: Binding(get: { code }, set: { value in
                    guard enabled, OtpRules.acceptsInput(value) else { return }
                    code = value // Single source of truth; no draft/model echo during rapid typing.
                }))
                    .font(VcType.body)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($focused)
                    .disabled(!enabled)
                    .accessibilityIdentifier("otp-system-input")
                Text("Nếu có SMS phù hợp, iOS có thể đề xuất mã trên bàn phím. Chọn mã hoặc nhập tay, rồi bấm Xong. Bạn vẫn cần bấm Xác nhận ở màn trước.")
                    .font(VcType.caption)
            }
            .navigationTitle("Nhập mã SMS")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Xong") { focused = false; dismiss() }
                }
            }
            .onAppear { focused = enabled }
            .onChange(of: enabled) { value in if !value { focused = false } }
        }
        .presentationDetents([.medium, .large])
    }
}
