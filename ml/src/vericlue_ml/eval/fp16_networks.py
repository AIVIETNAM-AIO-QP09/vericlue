"""GenD mixed FP16 adapter; normalization and classifier retain FP32 arithmetic."""

from __future__ import annotations

import copy

import torch
from torch import nn
from torch.nn import functional as F


class Float32LayerNorm(nn.Module):
    """Explicit casts keep ONNX and Torch normalization arithmetic aligned."""

    def __init__(self, original: nn.LayerNorm, *, half_output: bool = False) -> None:
        super().__init__()
        self.shape = original.normalized_shape
        self.eps = original.eps
        self.half_output = half_output
        self.register_buffer("weight", original.weight.detach().float().clone())
        self.register_buffer("bias", original.bias.detach().float().clone())

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return F.layer_norm(values.float(), self.shape, self.weight, self.bias, self.eps).to(
            torch.float16 if self.half_output else values.dtype
        )


class GendMixedHalf(nn.Module):
    """FP32 I/O; FP16 vision weights/activations; FP32 LayerNorm and output head."""

    def __init__(self, classifier, *, preserve_embeddings: bool = False) -> None:
        super().__init__()
        self.vision = classifier._vision
        self.input_half = not preserve_embeddings
        embeddings = (
            copy.deepcopy(self.vision.get_submodule("vision_model.embeddings"))
            if preserve_embeddings
            else None
        )
        # Save normalization weights BEFORE rounding the vision backbone to half.
        norms = {
            name: Float32LayerNorm(
                module, half_output=preserve_embeddings and name == "vision_model.pre_layrnorm"
            )
            for name, module in self.vision.named_modules()
            if isinstance(module, nn.LayerNorm)
        }
        self.vision.half()
        for name, norm in norms.items():
            self.vision.set_submodule(name, norm)
        if embeddings is not None:
            self.vision.set_submodule("vision_model.embeddings", embeddings)
        self.register_buffer("head_weight", classifier._weight.detach().float())
        self.register_buffer("head_bias", classifier._bias.detach().float())

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        pixels = images.to(torch.float16) if self.input_half else images.float()
        features = self.vision(pixel_values=pixels).pooler_output.float()
        logits = F.linear(F.normalize(features, p=2, dim=1), self.head_weight, self.head_bias)
        return logits, logits.softmax(dim=-1)
