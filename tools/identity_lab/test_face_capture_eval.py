import json
from types import SimpleNamespace

import face_capture_eval as module
import numpy as np
import pytest
from identity_lab import InputError


def test_mean_is_normalized_equal_weight_and_order_independent():
    vector, info = module.aggregate([[1.0, 0.0], [0.0, 2.0]])
    np.testing.assert_allclose(vector, [2**-0.5, 2**-0.5])
    reverse, _ = module.aggregate([[0.0, 2.0], [1.0, 0.0]])
    np.testing.assert_allclose(vector, reverse)
    assert info["frames"] == 2 and info["pairwise_cosine_min"] == 0


@pytest.mark.parametrize(
    "vectors",
    [
        [],
        [[1.0, 0.0]],
        [[1.0, 0.0], [-1.0, 0.0]],
        [[1.0, 0.0], [0.0, 0.0]],
        [[1.0, 0.0], [float("nan"), 1.0]],
    ],
)
def test_bad_bursts_rejected(vectors):
    with pytest.raises(ValueError):
        module.aggregate(vectors)


@pytest.mark.parametrize("bad_second", ["duplicate", "no_face"])
def test_bad_frame_blocks_burst_without_discarding_valid_pairs(tmp_path, monkeypatch, bad_second):
    paths = []
    for name, value in [
        ("ref", 1),
        ("selfie", 2),
        ("selfie2", 2 if bad_second == "duplicate" else 3),
    ]:
        path = tmp_path / name
        path.write_bytes(bytes([value]))
        paths.append(path)
    monkeypatch.setattr(
        module, "IdentityLab", lambda **kw: SimpleNamespace(_load_faces=lambda: None)
    )
    monkeypatch.setattr(module, "pipeline_config", lambda lab: {"test": True})
    monkeypatch.setattr(
        module, "decode_image", lambda data: np.full((2, 2, 3), data[0], dtype=np.uint8)
    )

    def extract(lab, image, role, debug):
        if image[0, 0, 0] == 3:
            raise InputError("E_NO_FACE_SELFIE")
        return np.array([1.0, 1.0]), {}

    monkeypatch.setattr(module, "extract_face", extract)
    out = tmp_path / "result"
    module.capture(paths[:1], paths[1:], out)
    result = json.loads((out / "report.json").read_text())
    assert result["burst"]["status"] == "retry"
    assert len(result["pairs"]) == 2
    assert [p["status"] for p in result["pairs"]] == ["ok", "retry"]
    assert result["identity_verified"] is False and result["threshold"] is None
