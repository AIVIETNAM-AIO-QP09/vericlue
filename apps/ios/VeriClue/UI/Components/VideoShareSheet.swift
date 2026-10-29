import Foundation
import SwiftUI
import UIKit

struct VideoShareItem: Identifiable {
    let id = UUID()
    let url: URL
}

struct VideoShareSheet: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        // Device checkpoint export is explicit. No automatic Photos or public upload.
        controller.excludedActivityTypes = [.saveToCameraRoll, .postToFacebook, .postToTwitter,
            .postToWeibo, .postToTencentWeibo, .assignToContact]
        return controller
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
