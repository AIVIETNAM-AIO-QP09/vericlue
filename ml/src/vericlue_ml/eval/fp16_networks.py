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

    def __init__(
        self, classifier, *, preserve_embeddings: bool = False, preserve_residuals: bool = False
    ) -> None:
        super().__init__()
        preserve_embeddings = preserve_embeddings or preserve_residuals
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
                module,
                half_output=preserve_embeddings
                and not preserve_residuals
                and name == "vision_model.pre_layrnorm",
            )
            for name, module in self.vision.named_modules()
            if isinstance(module, nn.LayerNorm)
        }
        self.vision.half()
        for name, norm in norms.items():
            self.vision.set_submodule(name, norm)
        if embeddings is not None:
            self.vision.set_submodule("vision_model.embeddings", embeddings)
        if preserve_residuals:
            linear_layers = {
                name: HalfLinearFloatOutput(module)
                for name, module in self.vision.named_modules()
                if isinstance(module, nn.Linear)
                and name != "vision_model.embeddings"
                and not name.startswith("vision_model.embeddings.")
            }
            for name, layer in linear_layers.items():
                self.vision.set_submodule(name, layer)
        self.register_buffer("head_weight", classifier._weight.detach().float())
        self.register_buffer("head_bias", classifier._bias.detach().float())

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        pixels = images.to(torch.float16) if self.input_half else images.float()
        features = self.vision(pixel_values=pixels).pooler_output.float()
        logits = F.linear(F.normalize(features, p=2, dim=1), self.head_weight, self.head_bias)
        return logits, logits.softmax(dim=-1)


class HalfLinearFloatOutput(nn.Module):
    """Half GEMM, then FP32 residual/activation/attention arithmetic."""

    def __init__(self, original: nn.Linear) -> None:
        super().__init__()
        self.register_buffer("weight", original.weight.detach())
        self.register_buffer("bias", original.bias.detach() if original.bias is not None else None)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        # A 2D linear exports as Gemm, preserving the fused bias rounding used by
        # Torch addmm. A 3D linear can export as separate half MatMul + half Add.
        flat = values.to(torch.float16).reshape(-1, self.weight.shape[1])
        output = F.linear(flat, self.weight, self.bias)
        return output.reshape(*values.shape[:-1], self.weight.shape[0]).float()
