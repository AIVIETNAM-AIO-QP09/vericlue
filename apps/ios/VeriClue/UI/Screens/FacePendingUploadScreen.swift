import SwiftUI

struct FacePendingUploadScreen: View {
    let onRoute: (Route) -> Void
    let onClose: () -> Void
    @EnvironmentObject private var face: FaceCaptureFlow

    var body: some View {
        VcScreen(step: 2) {
            VcTitleBlock(title: "Đang gửi dữ liệu", bodyText: "Giữ kết nối mạng để hoàn tất xác minh.")
            if face.stage == .uploading { ProgressView() }
            if let error = face.errorText { VcBanner(text: error, tone: .warning) }
            if face.retryUpload {
                VcPrimaryButton(title: "Thử lại") { Task { await face.submit() } }
            }
            if face.stage == .failed && !face.retryUpload {
                VcSecondaryButton(title: "Quay lại chuẩn bị") { onRoute(.faceExpired) }
            }
            VcSecondaryButton(title: "Dừng xác minh", action: onClose)
        }
        .navigationBarBackButtonHidden(true)
        .task {
            if !face.hasPendingCapture { onRoute(.faceExpired) }
            else { await face.submit() }
        }
        .onChange(of: face.destination) { route in if let route { onRoute(route) } }
    }
}
