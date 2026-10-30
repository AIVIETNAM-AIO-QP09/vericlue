"""GenD mixed FP16 adapter; normalization and classifier retain FP32 arithmetic."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class Float32LayerNorm(nn.Module):
    """Explicit casts keep ONNX and Torch normalization arithmetic aligned."""

    def __init__(self, original: nn.LayerNorm) -> None:
        super().__init__()
        self.shape = original.normalized_shape
        self.eps = original.eps
        self.register_buffer("weight", original.weight.detach().float().clone())
        self.register_buffer("bias", original.bias.detach().float().clone())

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return F.layer_norm(values.float(), self.shape, self.weight, self.bias, self.eps).to(
            values.dtype
        )


class GendMixedHalf(nn.Module):
    """FP32 I/O; FP16 vision weights/activations; FP32 LayerNorm and output head."""

    def __init__(self, classifier) -> None:
        super().__init__()
        self.vision = classifier._vision
        # Save normalization weights BEFORE rounding the vision backbone to half.
        norms = {
            name: Float32LayerNorm(module)
            for name, module in self.vision.named_modules()
            if isinstance(module, nn.LayerNorm)
        }
        self.vision.half()
        for name, norm in norms.items():
            self.vision.set_submodule(name, norm)
        self.register_buffer("head_weight", classifier._weight.detach().float())
        self.register_buffer("head_bias", classifier._bias.detach().float())

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.vision(pixel_values=images.to(torch.float16)).pooler_output.float()
        logits = F.linear(F.normalize(features, p=2, dim=1), self.head_weight, self.head_bias)
        return logits, logits.softmax(dim=-1)
