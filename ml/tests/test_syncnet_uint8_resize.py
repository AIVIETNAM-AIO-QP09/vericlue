"""Model-free pixel parity with LatentSync's pinned uint8 TorchVision resize.

Reference: LatentSync@a229c3948406bc2cf6eaf4873e662e70c6a04746,
latentsync/utils/image_processor.py::process_images; torchvision@v0.20.1,
transforms/_functional_tensor.py::resize and _cast_squeeze_out. The reference
resizes in float, saturates and rounds back to uint8, then normalizes the bytes.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.voice.syncnet import StableBackend


@pytest.mark.parametrize("height,width", [(191, 233), (319, 287), (256, 256)])
def test_visual_encoder_receives_upstream_rgb_bytes_after_resize(height, width):
    """Catch lost byte rounding while preserving frame/channel/row packing."""
    torch = pytest.importorskip("torch")
    from torch.nn.functional import interpolate

    y, x = np.indices((height, width))
    crops = [
        np.stack(
            [
                (x * 17 + y * 29 + frame * 11) % 256,
                (x * 7 + y * 3 + frame * 13 + 37) % 256,
                np.where((x + y + frame) % 2, 0, 255),
            ],
            axis=-1,
        ).astype(np.uint8)
        for frame in range(16)
    ]

    # Independent byte conversion uses NumPy's ties-to-even rounding. Only the
    # documented interpolation primitive is shared with the production path.
    rgb_frames = torch.from_numpy(np.stack(crops)).permute(0, 3, 1, 2)
    resized = interpolate(
        rgb_frames.float(),
        size=(256, 256),
        mode="bicubic",
        align_corners=False,
        antialias=True,
    )
    reference_bytes = np.rint(np.clip(resized.numpy(), 0, 255)).astype(np.uint8)
    normalized = (torch.from_numpy(reference_bytes).float() / 255.0 - 0.5) / 0.5
    expected = torch.cat(list(normalized), dim=0)[None, :, 128:, :]

    received = []

    def visual_encoder(tensor):
        received.append(tensor.detach().clone())
        return torch.ones((1, 2, 1, 1))

    backend = StableBackend()
    backend.model = SimpleNamespace(visual_encoder=visual_encoder)
    embedding = backend.embed_video(crops)

    assert len(received) == 1
    actual = received[0]
    assert actual.shape == (1, 48, 128, 256)
    assert actual.dtype == torch.float32
    assert actual.min() >= -1 and actual.max() <= 1
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    np.testing.assert_allclose(embedding, np.full(2, 1 / np.sqrt(2)), rtol=1e-6)
