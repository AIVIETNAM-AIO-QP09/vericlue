"""Torch-only export adapters retaining the production classifiers' class ordering."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class FasExport(nn.Module):
    """Export the unchanged FS-VFM network, including its cosine-normalized head."""

    def __init__(self, classifier) -> None:
        super().__init__()
        self.network = classifier.network

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.network(images)
        return logits, logits.softmax(dim=-1)


class GendExport(nn.Module):
    """Retain CLIP pooler output, L2 normalization and the learned two-class head."""

    def __init__(self, classifier) -> None:
        super().__init__()
        self.vision = classifier._vision
        self.register_buffer("head_weight", classifier._weight)
        self.register_buffer("head_bias", classifier._bias)

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.vision(pixel_values=images).pooler_output
        logits = F.linear(F.normalize(features, p=2, dim=1), self.head_weight, self.head_bias)
        return logits, logits.softmax(dim=-1)


def load_network(model: str, root, device: str):
    """Reuse verified production loaders rather than loading arbitrary pickle files."""
    from vericlue_ml.face.fsvfm import load_classifier
    from vericlue_ml.face.gend import _load_classifier

    if model == "fsvfm":
        classifier, revision = load_classifier(root, device)
        network = FasExport(classifier)
        revisions = {"fs-vfm-vit-l-fas": revision}
    elif model == "gend":
        classifier, revision, clip_revision = _load_classifier(root, device)
        network = GendExport(classifier)
        revisions = {"gend-clip-l14": revision, "clip-vit-large-patch14": clip_revision}
    else:
        raise ValueError("Unsupported model")
    network.eval()
    if any(
        t.dtype != torch.float32
        for t in (*network.parameters(), *network.buffers())
        if t.is_floating_point()
    ):
        raise ValueError("Expected original FP32 weights")
    return network, classifier, revisions
