import SwiftUI
import UIKit

// Stable backing view; paint directly for the display link's targetTimestamp.
final class FaceTimelineCanvasView: UIView {
    private let halo = CALayer()
    private let dot = CALayer()
    private var dotPosition: CGPoint?

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false
        halo.backgroundColor = UIColor(VcPalette.primary).withAlphaComponent(0.18).cgColor
        dot.backgroundColor = UIColor(VcPalette.primary).cgColor
        layer.addSublayer(halo); layer.addSublayer(dot)
        paint(rgb: FaceTimeline.grey, dot: nil)
    }

    required init?(coder: NSCoder) { nil }

    func paint(rgb: TimelineRGB, dot position: CGPoint?) {
        CATransaction.begin(); CATransaction.setDisableActions(true)
        backgroundColor = UIColor(red: rgb.r, green: rgb.g, blue: rgb.b, alpha: 1)
        dotPosition = position
        positionDot()
        CATransaction.commit()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        CATransaction.begin(); CATransaction.setDisableActions(true)
        positionDot(); CATransaction.commit()
    }

    private func positionDot() {
        halo.isHidden = dotPosition == nil; dot.isHidden = dotPosition == nil
        guard let position = dotPosition else { return }
        // Safe-area coordinates of the full display, not the mirrored camera box.
        let area = bounds.inset(by: safeAreaInsets)
        let center = CGPoint(x: area.minX + position.x * area.width, y: area.minY + position.y * area.height)
        halo.bounds = CGRect(x: 0, y: 0, width: 48, height: 48); halo.cornerRadius = 24; halo.position = center
        dot.bounds = CGRect(x: 0, y: 0, width: 28, height: 28); dot.cornerRadius = 14; dot.position = center
    }
}

struct FaceTimelineCanvas: UIViewRepresentable {
    let flow: FaceCaptureFlow
    func makeUIView(context: Context) -> FaceTimelineCanvasView {
        let view = FaceTimelineCanvasView()
        flow.canvas = view
        return view
    }
    func updateUIView(_ view: FaceTimelineCanvasView, context: Context) {}
    static func dismantleUIView(_ view: FaceTimelineCanvasView, coordinator: ()) { view.paint(rgb: FaceTimeline.grey, dot: nil) }
}
