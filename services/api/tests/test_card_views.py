import cv2
import numpy as np

from vericlue_api.services.card_views import rectified_card_views


def synthetic_card():
    card = np.full((400, 640, 3), 235, np.uint8)
    # Synthetic text only: no personal document or face fixtures.
    qr = cv2.QRCodeEncoder_create().encode("VERICLUE-SYNTHETIC-CARD-VIEW")
    qr = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    qr = cv2.resize(qr, (230, 230), interpolation=cv2.INTER_NEAREST)
    card[80:310, 360:590] = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
    return card


def test_perspective_view_preserves_decodable_pixels():
    card = synthetic_card()
    source = np.float32([[0, 0], [639, 0], [639, 399], [0, 399]])
    target = np.float32([[100, 100], [760, 160], [690, 560], [140, 500]])
    tilted = cv2.warpPerspective(card, cv2.getPerspectiveTransform(source, target), (900, 650))
    views = rectified_card_views(tilted)
    assert 1 <= len(views) <= 2
    assert any(
        cv2.QRCodeDetector().detectAndDecode(view)[0] == "VERICLUE-SYNTHETIC-CARD-VIEW"
        for view in views
    )
    assert all(max(view.shape[:2]) <= 2560 for view in views)


def test_flat_background_and_small_shapes_do_not_become_cards():
    assert rectified_card_views(np.full((400, 640, 3), 230, np.uint8)) == []
    image = np.zeros((600, 900, 3), np.uint8)
    cv2.rectangle(image, (10, 10), (90, 60), (255, 255, 255), -1)
    assert rectified_card_views(image) == []
