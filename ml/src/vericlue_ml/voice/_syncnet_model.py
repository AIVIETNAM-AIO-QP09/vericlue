# Copyright (c) 2024 Bytedance Ltd. and/or its affiliates
# Copyright 2024 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Modified: inference-only, inline attention/GEGLU, tensor reshapes instead of einops,
# optional pinned configuration and separate normalized modality encoders.
# SPDX-License-Identifier: Apache-2.0
"""Minimal state-dict-compatible LatentSync stable_syncnet architecture.

LatentSync@a229c3948406bc2cf6eaf4873e662e70c6a04746:
latentsync/models/stable_syncnet.py, latentsync/models/attention.py (Attention),
configs/syncnet/syncnet_16_pixel_attn.yaml. FeedForward/GEGLU adapted from
Diffusers@560fb5f4d65b8593c13e4be50a59b1fd9c2d9992 (v0.32.2):
src/diffusers/models/attention.py and activations.py. Both sources Apache-2.0;
see third_party/licenses/latentsync-Apache-2.0.txt and diffusers-Apache-2.0.txt.

No checkpoint, network, video processing or model instance is created on import.
The caller imports this helper lazily, verifies the local checkpoint and loads it
strictly. The weights have a separate OpenRAIL++ license in models/manifest.yaml.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

STABLE_SYNCNET_CONFIG = {
    "audio_encoder": {
        "in_channels": 1,
        "block_out_channels": [32, 64, 128, 256, 512, 1024, 2048],
        "downsample_factors": [[2, 1], 2, 2, 1, 2, 2, [2, 3]],
        "attn_blocks": [0, 0, 0, 1, 1, 0, 0],
        "dropout": 0.0,
    },
    "visual_encoder": {
        "in_channels": 48,
        "block_out_channels": [64, 128, 256, 256, 512, 1024, 2048, 2048],
        "downsample_factors": [[1, 2], 2, 2, 2, 2, 2, 2, 2],
        "attn_blocks": [0, 0, 0, 0, 1, 1, 0, 0],
        "dropout": 0.0,
    },
}


class _GEGLU(nn.Module):
    def __init__(self, dim_in: int, dim_out: int) -> None:
        super().__init__()
        self.proj = nn.Linear(dim_in, dim_out * 2)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        hidden_states, gate = self.proj(hidden_states).chunk(2, dim=-1)
        return hidden_states * F.gelu(gate)


class _FeedForward(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.0) -> None:
        super().__init__()
        # Keep Diffusers' net.0.proj / net.2 keys exactly as stored in the checkpoint.
        self.net = nn.ModuleList(
            [_GEGLU(dim, dim * 4), nn.Dropout(dropout), nn.Linear(dim * 4, dim)]
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        for layer in self.net:
            hidden_states = layer(hidden_states)
        return hidden_states


class _Attention(nn.Module):
    def __init__(self, query_dim: int, heads: int = 8, dropout: float = 0.0) -> None:
        super().__init__()
        self.heads = heads
        self.to_q = nn.Linear(query_dim, query_dim, bias=True)
        self.to_k = nn.Linear(query_dim, query_dim, bias=True)
        self.to_v = nn.Linear(query_dim, query_dim, bias=True)
        self.to_out = nn.ModuleList([nn.Linear(query_dim, query_dim), nn.Dropout(dropout)])

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        batch, length, channels = hidden_states.shape

        def split_heads(tensor: torch.Tensor) -> torch.Tensor:
            return tensor.reshape(batch, length, self.heads, channels // self.heads).permute(
                0, 2, 1, 3
            )

        query = split_heads(self.to_q(hidden_states))
        key = split_heads(self.to_k(hidden_states))
        value = split_heads(self.to_v(hidden_states))
        hidden_states = F.scaled_dot_product_attention(query, key, value)
        hidden_states = hidden_states.permute(0, 2, 1, 3).reshape(batch, length, channels)
        return self.to_out[1](self.to_out[0](hidden_states))


class _ResnetBlock2D(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        dropout: float,
        downsample_factor: int | list[int],
    ) -> None:
        super().__init__()
        self.norm1 = nn.GroupNorm(32, in_channels, eps=1e-6, affine=True)
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride=1, padding=1)
        self.norm2 = nn.GroupNorm(32, out_channels, eps=1e-6, affine=True)
        self.dropout = nn.Dropout(dropout)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, stride=1, padding=1)
        self.act_fn = nn.SiLU()
        self.conv_shortcut = (
            nn.Conv2d(in_channels, out_channels, 1) if in_channels != out_channels else None
        )
        if isinstance(downsample_factor, list):
            downsample_factor = tuple(downsample_factor)
        self.downsample_conv = (
            None
            if downsample_factor == 1
            else nn.Conv2d(out_channels, out_channels, 3, stride=downsample_factor, padding=0)
        )
        self.pad = (0, 1, 0, 1)
        if isinstance(downsample_factor, tuple):
            if downsample_factor[0] == 1:
                self.pad = (0, 1, 1, 1)
            elif downsample_factor[1] == 1:
                self.pad = (1, 1, 0, 1)

    def forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        hidden_states = self.conv1(self.act_fn(self.norm1(input_tensor)))
        hidden_states = self.conv2(self.dropout(self.act_fn(self.norm2(hidden_states))))
        if self.conv_shortcut is not None:
            input_tensor = self.conv_shortcut(input_tensor)
        hidden_states = hidden_states + input_tensor
        if self.downsample_conv is not None:
            hidden_states = self.downsample_conv(
                F.pad(hidden_states, self.pad, mode="constant", value=0)
            )
        return hidden_states


class _AttentionBlock2D(nn.Module):
    def __init__(self, query_dim: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.norm1 = nn.GroupNorm(32, query_dim, eps=1e-6, affine=True)
        self.norm2 = nn.LayerNorm(query_dim)
        self.norm3 = nn.LayerNorm(query_dim)
        self.ff = _FeedForward(query_dim, dropout)
        self.conv_in = nn.Conv2d(query_dim, query_dim, 1)
        self.conv_out = nn.Conv2d(query_dim, query_dim, 1)
        self.attn = _Attention(query_dim, heads=8, dropout=dropout)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        batch, channels, height, width = hidden_states.shape
        residual = hidden_states
        hidden_states = self.conv_in(self.norm1(hidden_states)).flatten(2).transpose(1, 2)
        hidden_states = self.attn(self.norm2(hidden_states)) + hidden_states
        hidden_states = self.ff(self.norm3(hidden_states)) + hidden_states
        hidden_states = (
            hidden_states.transpose(1, 2).reshape(batch, channels, height, width).contiguous()
        )
        return self.conv_out(hidden_states) + residual


class _DownEncoder2D(nn.Module):
    def __init__(
        self,
        in_channels: int,
        block_out_channels: list[int],
        downsample_factors: list[int | list[int]],
        attn_blocks: list[int],
        dropout: float,
    ) -> None:
        super().__init__()
        self.conv_in = nn.Conv2d(in_channels, block_out_channels[0], 3, stride=1, padding=1)
        self.down_blocks = nn.ModuleList()
        output_channels = block_out_channels[0]
        for index, block_out_channel in enumerate(block_out_channels):
            input_channels, output_channels = output_channels, block_out_channel
            self.down_blocks.append(
                _ResnetBlock2D(input_channels, output_channels, dropout, downsample_factors[index])
            )
            if attn_blocks[index] == 1:
                self.down_blocks.append(_AttentionBlock2D(output_channels, dropout))
        self.norm_out = nn.GroupNorm(32, block_out_channels[-1], eps=1e-6)
        self.act_fn_out = nn.ReLU()

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        hidden_states = self.conv_in(hidden_states)
        for block in self.down_blocks:
            hidden_states = block(hidden_states)
        return self.act_fn_out(self.norm_out(hidden_states))


class StableSyncNet(nn.Module):
    """Torch-only inference architecture with original audio/visual state_dict keys."""

    def __init__(self, config: dict | None = None, gradient_checkpointing: bool = False) -> None:
        super().__init__()
        if gradient_checkpointing:
            raise ValueError("This SyncNet helper supports inference only")
        config = STABLE_SYNCNET_CONFIG if config is None else config
        self.audio_encoder = _DownEncoder2D(**config["audio_encoder"])
        self.visual_encoder = _DownEncoder2D(**config["visual_encoder"])
        self.eval()

    def encode_audio(self, audio_sequences: torch.Tensor) -> torch.Tensor:
        """Return the normalized audio embeddings for cached temporal candidates."""
        return F.normalize(self.audio_encoder(audio_sequences).flatten(1), p=2, dim=1)

    def encode_video(self, image_sequences: torch.Tensor) -> torch.Tensor:
        """Return the normalized visual embeddings for a 16-frame lower-face window."""
        return F.normalize(self.visual_encoder(image_sequences).flatten(1), p=2, dim=1)

    def forward(
        self, image_sequences: torch.Tensor, audio_sequences: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return self.encode_video(image_sequences), self.encode_audio(audio_sequences)
