import numpy as np
import pytest
from audit_face_portrait import portrait_region


def test_portrait_expands_and_clips_without_losing_original_box():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    crop, roi = portrait_region(image, [10, 20, 70, 80])
    assert roi == [0, 0, 100, 100]
    assert crop.shape == (100, 100, 3)
    crop, roi = portrait_region(image, [100, 30, 140, 60])
    assert roi == [80, 15, 160, 75]
    assert np.shares_memory(crop, image)


@pytest.mark.parametrize("bbox", [[0, 0, 0, 10], [0, 0, float("nan"), 10], [400, 400, 410, 410]])
def test_bad_portrait_box_rejected(bbox):
    with pytest.raises(ValueError):
        portrait_region(np.zeros((100, 100, 3), dtype=np.uint8), bbox)
