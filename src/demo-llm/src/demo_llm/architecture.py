#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Block 3: a decoder-only transformer, small enough to fit under 1M parameters.
Written out rather than assembled from nn.TransformerEncoder. 
The shapes below use:
    B = batch, T = sequence length, C = d_model, H = n_head, hs = C // H
"""

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
from torch.nn import functional as F


@dataclass
class Config:
    vocab_size: int = 2048
    # 2048 keeps the <|sys:k|><|tools|> header inside the window for 90% of
    # trajectories. Affordable at any size because RoPE costs no parameters.
    context: int = 2048
    n_layer: int = 6
    n_head: int = 8
    d_model: int = 256
    dropout: float = 0.1
    rope_base: float = 10000.0
    flash: bool = True


# head dimension must be even for RoPE
# to have whole pairs to rotate.
PRESETS = {
    "tiny": dict(d_model=128, n_layer=3, n_head=4),
    "small": dict(d_model=256, n_layer=6, n_head=8),
    "medium": dict(d_model=384, n_layer=8, n_head=6),
    "large": dict(d_model=512, n_layer=12, n_head=8),
}


def build_rope_cache(head_dim, max_seq, base=10000.0):
    """Precomputed cos/sin for rotary position embeddings."""
    inv_freq = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
    angles = torch.outer(torch.arange(max_seq).float(), inv_freq)  # (T, hs/2)
    return torch.cos(angles), torch.sin(angles)


def apply_rope(x, cos, sin):
    """Rotate each adjacent dimension pair of x."""
    T = x.size(2)
    cos, sin = cos[:T].view(1, 1, T, -1), sin[:T].view(1, 1, T, -1)
    x_even, x_odd = x[..., 0::2], x[..., 1::2]
    out = torch.stack(
        (x_even * cos - x_odd * sin, x_even * sin + x_odd * cos), dim=-1
    )
    return out.flatten(-2)


class CausalSelfAttention(nn.Module):
    """Each position mixes in information from positions at or before it."""

    def __init__(self, cfg):
        super().__init__()
        assert cfg.d_model % cfg.n_head == 0
        self.n_head = cfg.n_head
        self.d_model = cfg.d_model
        self.flash = cfg.flash
        self.dropout_p = cfg.dropout
        # one matrix producing query, key and value together, then split
        self.c_attn = nn.Linear(cfg.d_model, 3 * cfg.d_model)
        self.c_proj = nn.Linear(cfg.d_model, cfg.d_model)
        self.attn_dropout = nn.Dropout(cfg.dropout)
        self.resid_dropout = nn.Dropout(cfg.dropout)
        # Lower-triangular mask
        if not self.flash:
            self.register_buffer(
                "mask",
                torch.tril(torch.ones(cfg.context, cfg.context, dtype=torch.bool))
                .view(1, 1, cfg.context, cfg.context),
                persistent=False,
            )

    def forward(self, x, cos, sin):
        B, T, C = x.shape
        hs = C // self.n_head

        q, k, v = self.c_attn(x).split(C, dim=2)
        # (B, T, C) -> (B, H, T, hs) so each head attends independently
        q = q.view(B, T, self.n_head, hs).transpose(1, 2)
        k = k.view(B, T, self.n_head, hs).transpose(1, 2)
        v = v.view(B, T, self.n_head, hs).transpose(1, 2)

        # Position enters here, by rotating q and k - not by adding a learned v
        q, k = apply_rope(q, cos, sin), apply_rope(k, cos, sin)

        if self.flash:
            y = F.scaled_dot_product_attention(
                q, k, v, is_causal=True,
                dropout_p=self.dropout_p if self.training else 0.0,
            )
        else:
            # scaled dot-product: dividing by sqrt(hs) keeps the variance of the
            # scores at ~1 regardless of head size, so softmax does not saturate
            att = (q @ k.transpose(-2, -1)) / math.sqrt(hs)
            att = att.masked_fill(~self.mask[:, :, :T, :T], float("-inf"))
            att = self.attn_dropout(F.softmax(att, dim=-1))
            y = att @ v

        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_dropout(self.c_proj(y))


class MLP(nn.Module):
    """Per-position transformation"""

    def __init__(self, cfg):
        super().__init__()
        self.c_fc = nn.Linear(cfg.d_model, 4 * cfg.d_model)
        self.c_proj = nn.Linear(4 * cfg.d_model, cfg.d_model)
        self.dropout = nn.Dropout(cfg.dropout)

    def forward(self, x):
        return self.dropout(self.c_proj(F.gelu(self.c_fc(x))))


class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.ln_1 = nn.LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln_2 = nn.LayerNorm(cfg.d_model)
        self.mlp = MLP(cfg)

    def forward(self, x, cos, sin):
        x = x + self.attn(self.ln_1(x), cos, sin)
        x = x + self.mlp(self.ln_2(x))
        return x


class TinyGPT(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.wte = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList(Block(cfg) for _ in range(cfg.n_layer))
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)

        cos, sin = build_rope_cache(cfg.d_model // cfg.n_head, cfg.context, cfg.rope_base)
        self.register_buffer("rope_cos", cos, persistent=False)
        self.register_buffer("rope_sin", sin, persistent=False)

        self.lm_head.weight = self.wte.weight

        self.apply(self._init_weights)
        for name, p in self.named_parameters():
            if name.endswith("c_proj.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * cfg.n_layer))

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx, targets=None):
        B, T = idx.shape
        assert T <= self.cfg.context, f"sequence of {T} exceeds context {self.cfg.context}"

        x = self.drop(self.wte(idx))
        for block in self.blocks:
            x = block(x, self.rope_cos, self.rope_sin)
        logits = self.lm_head(self.ln_f(x))

        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)), targets.reshape(-1), ignore_index=-1
            )
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None, stop_id=None):
        """stop_id may be a single token id or any collection of them."""
        was_training = self.training
        self.eval()
        if stop_id is not None and not hasattr(stop_id, "__iter__"):
            stop_id = [stop_id]
        try:
            return self._generate(idx, max_new_tokens, temperature, top_k, stop_id)
        finally:
            self.train(was_training)

    def _generate(self, idx, max_new_tokens, temperature, top_k, stop_id):
        for _ in range(max_new_tokens):
            # crop to the context window; the model cannot see further back
            window = idx[:, -self.cfg.context:]
            logits, _ = self(window)
            logits = logits[:, -1, :] / max(temperature, 1e-6)
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")
            nxt = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
            idx = torch.cat((idx, nxt), dim=1)
            if stop_id is not None and all(int(t) in stop_id for t in nxt.flatten()):
                break
        return idx

    def param_breakdown(self):
        groups = {
            "token embeddings (tied)": self.wte.weight.numel(),
            "position (RoPE, buffers)": 0,
            "blocks": sum(p.numel() for p in self.blocks.parameters()),
            "final layernorm": sum(p.numel() for p in self.ln_f.parameters()),
        }
        groups["TOTAL"] = sum(groups.values())
        return groups
