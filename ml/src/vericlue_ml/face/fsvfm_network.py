"""Independent PyTorch reconstruction of the published FS-VFM FAS tensor layout.

Architecture reference: wolo-wolo/FSFM-CVPR25@b84aafa2507c30bb4986564de8262969647e450c,
fsvfm/finetune/cross_domain_FAS/{fas,models_vit}.py. No upstream code is imported
or vendored. Keep torch imports isolated from the normal CPU-only CI package.
"""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn
from torch.nn import functional as F


class FasNetwork(nn.Module):
    """ViT-L/16, patch-mean token, token-axis bottleneck and two-class head."""

    def __init__(
        self,
        *,
        width: int = 1024,
        depth: int = 24,
        heads: int = 16,
        hidden: int = 512,
        image_size: int = 224,
        patch_size: int = 16,
    ) -> None:
        super().__init__()
        self.patch = nn.Conv2d(3, width, patch_size, stride=patch_size)
        self.cls = nn.Parameter(torch.zeros(1, 1, width))
        self.position = nn.Parameter(torch.zeros(1, (image_size // patch_size) ** 2 + 1, width))
        self.layers = nn.ModuleList(
            nn.TransformerEncoderLayer(
                width,
                heads,
                width * 4,
                dropout=0,
                activation="gelu",
                batch_first=True,
                norm_first=True,
                layer_norm_eps=1e-6,
            )
            for _ in range(depth)
        )
        self.pool_norm = nn.LayerNorm(width, eps=1e-6)
        self.bottleneck = nn.Linear(width, hidden)
        self.classifier = nn.Linear(hidden, 2)

    def classify_tokens(self, tokens: torch.Tensor) -> torch.Tensor:
        """Preserve the unusual token-axis normalization used by the FAS checkpoint."""
        pooled = self.pool_norm(tokens[:, 1:].mean(dim=1))
        tokens = torch.cat((pooled.unsqueeze(1), tokens[:, 1:]), dim=1)
        features = F.relu(self.bottleneck(tokens))
        denominator = features.norm(dim=1, keepdim=True).clamp_min(1e-12).sqrt() * 2**0.5
        features = features / denominator
        weights = self.classifier.weight / self.classifier.weight.norm(dim=0, keepdim=True)
        return F.linear(features[:, 0], weights, self.classifier.bias)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        tokens = self.patch(images).flatten(2).transpose(1, 2)
        tokens = torch.cat((self.cls.expand(images.shape[0], -1, -1), tokens), dim=1)
        tokens = tokens + self.position
        for layer in self.layers:
            tokens = layer(tokens)
        return self.classify_tokens(tokens)


def checkpoint_state(
    source: Mapping[str, torch.Tensor], depth: int = 24
) -> dict[str, torch.Tensor]:
    """Translate every tensor strictly; reject unexpected keys and conflicting aliases."""
    source = dict(source)
    target = {}

    def move(old, new):
        target[new] = source.pop(old)

    for old, new in (
        ("cls_token", "cls"),
        ("pos_embed", "position"),
        ("patch_embed.proj.weight", "patch.weight"),
        ("patch_embed.proj.bias", "patch.bias"),
        ("fc_norm.weight", "pool_norm.weight"),
        ("fc_norm.bias", "pool_norm.bias"),
    ):
        move("backbone.vit." + old, new)
    for i in range(depth):
        for old, new in (
            ("attn.qkv.weight", "self_attn.in_proj_weight"),
            ("attn.qkv.bias", "self_attn.in_proj_bias"),
            ("attn.proj.weight", "self_attn.out_proj.weight"),
            ("attn.proj.bias", "self_attn.out_proj.bias"),
            ("mlp.fc1.weight", "linear1.weight"),
            ("mlp.fc1.bias", "linear1.bias"),
            ("mlp.fc2.weight", "linear2.weight"),
            ("mlp.fc2.bias", "linear2.bias"),
            ("norm1.weight", "norm1.weight"),
            ("norm1.bias", "norm1.bias"),
            ("norm2.weight", "norm2.weight"),
            ("norm2.bias", "norm2.bias"),
        ):
            move(f"backbone.vit.blocks.{i}.{old}", f"layers.{i}.{new}")
    for suffix in ("weight", "bias"):
        canonical = f"embedder.bottleneck_layer_fc.{suffix}"
        alias = source.pop(f"embedder.bottleneck_layer.0.{suffix}")
        if not torch.equal(alias, source[canonical]):
            raise ValueError("Conflicting bottleneck aliases")
        move(canonical, f"bottleneck.{suffix}")
        move(f"classifier.classifier_layer.{suffix}", f"classifier.{suffix}")
    if source:
        raise ValueError("Unexpected checkpoint tensors")
    if any(
        not torch.is_floating_point(value) or value.dtype != torch.float32
        for value in target.values()
    ):
        raise ValueError("Expected original FP32 tensors")
    return target
