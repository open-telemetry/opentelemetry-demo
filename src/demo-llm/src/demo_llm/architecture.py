"""
Block 3: a decoder-only transformer, small enough to fit under 5M parameters.
"""

import math
import time
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


PRESETS = {
    "tiny": dict(d_model=128, n_layer=3, n_head=4),
    "small": dict(d_model=256, n_layer=6, n_head=8),
    "medium": dict(d_model=384, n_layer=8, n_head=6),
    "large": dict(d_model=512, n_layer=12, n_head=8),
}


def build_rope_cache(head_dim, max_seq, base=10000.0):
    inv_freq = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
    angles = torch.outer(torch.arange(max_seq).float(), inv_freq)  # (T, hs/2)
    return torch.cos(angles), torch.sin(angles)


def apply_rope(x, cos, sin, pos=0):
    T = x.size(2)
    cos = cos[pos:pos + T].view(1, 1, T, -1)
    sin = sin[pos:pos + T].view(1, 1, T, -1)
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

        if not self.flash:
            self.register_buffer(
                "mask",
                torch.tril(torch.ones(cfg.context, cfg.context, dtype=torch.bool))
                .view(1, 1, cfg.context, cfg.context),
                persistent=False,
            )

    def forward(self, x, cos, sin, past=None):
        B, T, C = x.shape
        hs = C // self.n_head

        q, k, v = self.c_attn(x).split(C, dim=2)
        # (B, T, C) -> (B, H, T, hs) so each head attends independently
        q = q.view(B, T, self.n_head, hs).transpose(1, 2)
        k = k.view(B, T, self.n_head, hs).transpose(1, 2)
        v = v.view(B, T, self.n_head, hs).transpose(1, 2)

        # Position enters here, by rotating q and k
        pos = 0 if past is None else past[0].size(2)
        q, k = apply_rope(q, cos, sin, pos), apply_rope(k, cos, sin, pos)

        if past is not None:
            k = torch.cat((past[0], k), dim=2)
            v = torch.cat((past[1], v), dim=2)
        present = (k, v)
        causal = q.size(2) == k.size(2)

        if self.flash:
            y = F.scaled_dot_product_attention(
                q, k, v, is_causal=causal,
                dropout_p=self.dropout_p if self.training else 0.0,
            )
        else:
            att = (q @ k.transpose(-2, -1)) / math.sqrt(hs)
            if causal:
                att = att.masked_fill(~self.mask[:, :, :T, :T], float("-inf"))
            att = self.attn_dropout(F.softmax(att, dim=-1))
            y = att @ v

        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_dropout(self.c_proj(y)), present


class MLP(nn.Module):
    """Per-position transformation. Widening to 4x is where most of the
    per-layer parameters live, and where most factual recall is thought to sit."""

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

    def forward(self, x, cos, sin, past=None):
        a, present = self.attn(self.ln_1(x), cos, sin, past)
        x = x + a
        x = x + self.mlp(self.ln_2(x))
        return x, present


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

    def forward(self, idx, targets=None, past=None, use_cache=False):
        B, T = idx.shape
        pos = 0 if past is None else past[0][0].size(2)
        assert pos + T <= self.cfg.context, \
            f"sequence of {pos + T} exceeds context {self.cfg.context}"

        x = self.drop(self.wte(idx))
        presents = []
        for i, block in enumerate(self.blocks):
            x, present = block(x, self.rope_cos, self.rope_sin,
                               None if past is None else past[i])
            presents.append(present)
        logits = self.lm_head(self.ln_f(x))

        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)), targets.reshape(-1), ignore_index=-1
            )
        return (logits, loss, presents) if use_cache else (logits, loss)

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None,
                 stop_id=None, use_cache=True):
        was_training = self.training
        self.eval()
        if stop_id is not None and not hasattr(stop_id, "__iter__"):
            stop_id = [stop_id]
        try:
            gen = self._generate_cached if use_cache else self._generate
            return gen(idx, max_new_tokens, temperature, top_k, stop_id)
        finally:
            self.train(was_training)

    def _sample(self, logits, temperature, top_k):
        logits = logits[:, -1, :] / max(temperature, 1e-6)
        if top_k is not None:
            v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < v[:, [-1]]] = float("-inf")
        return torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)

    def _generate_cached(self, idx, max_new_tokens, temperature, top_k, stop_id):
        room = self.cfg.context - max_new_tokens
        cur = idx[:, -room:] if idx.size(1) > room else idx
        past = None
        for _ in range(max_new_tokens):
            logits, _, past = self(cur, past=past, use_cache=True)
            nxt = self._sample(logits, temperature, top_k)
            idx = torch.cat((idx, nxt), dim=1)
            cur = nxt
            if stop_id is not None and all(int(t) in stop_id for t in nxt.flatten()):
                break
            if past[0][0].size(2) >= self.cfg.context:
                break
        return idx

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


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS), default="small")
    ap.add_argument("--compare", action="store_true", help="table of every preset")
    args = ap.parse_args()

    if args.compare:
        print(f"{'preset':<10}{'d_model':>9}{'layers':>8}{'heads':>7}"
              f"{'params':>13}{'fp32':>9}{'tok/param':>11}")
        print("-" * 67)
        for name, over in PRESETS.items():
            m = TinyGPT(Config(**over))
            n = m.param_breakdown()["TOTAL"]
            print(f"{name:<10}{over['d_model']:>9}{over['n_layer']:>8}{over['n_head']:>7}"
                  f"{n:>13,}{n * 4 / 1e6:>8.1f}M{291_745 / n:>11.2f}")
        print()
        print("tok/param is training tokens per parameter. Chinchilla-optimal is ~20;")
        print("everything here is heavily over-parameterised, which is what memorising needs.")
        return

    cfg = Config(**PRESETS[args.preset])
    model = TinyGPT(cfg)

    print(f"preset '{args.preset}':  vocab {cfg.vocab_size}  d_model {cfg.d_model}  "
          f"layers {cfg.n_layer}  heads {cfg.n_head}  context {cfg.context}")
    print()
    groups = model.param_breakdown()
    total = groups["TOTAL"]
    for name, n in groups.items():
        if name == "TOTAL":
            print("-" * 52)
            print(f"{'TOTAL':<28}{n:>12,}{'':>10}")
        else:
            print(f"{name:<28}{n:>12,}{n / total:>9.0%}")
    print()
    print(f"fp32 size: {total * 4 / 1e6:.1f} MB   fp16: {total * 2 / 1e6:.1f} MB")
    print(f"per-block: {groups['blocks'] // cfg.n_layer:,}   "
          f"(formula 12*d^2 = {12 * cfg.d_model ** 2:,}, plus biases and layernorms)")

    print()
    print("SANITY CHECKS")
    model.eval()
    idx = torch.randint(0, cfg.vocab_size, (2, 64))

    targets = torch.randint(0, cfg.vocab_size, (2, 64))
    logits, loss = model(idx, targets=targets)
    print(f"  forward shapes    : {tuple(idx.shape)} -> {tuple(logits.shape)}")

    print(f"  initial loss      : {loss.item():.3f}   (expected ~{math.log(cfg.vocab_size):.3f} = ln(vocab))")

    a = model(idx)[0]
    idx2 = idx.clone()
    idx2[:, -1] = (idx2[:, -1] + 1) % cfg.vocab_size
    b = model(idx2)[0]
    delta = (a[:, :-1] - b[:, :-1]).abs().max().item()
    print(f"  causal mask holds : max change to earlier logits = {delta:.2e}")

    hs = cfg.d_model // cfg.n_head
    cos, sin = build_rope_cache(hs, cfg.context, cfg.rope_base)
    torch.manual_seed(0)
    qv, kv = torch.randn(1, 1, 1, hs), torch.randn(1, 1, 1, hs)

    def score(i, j):
        qi = apply_rope(qv, cos[i:i + 1], sin[i:i + 1])
        kj = apply_rope(kv, cos[j:j + 1], sin[j:j + 1])
        return (qi * kj).sum().item()

    pairs = [(5, 3), (10, 8), (100, 98), (1000, 998)]
    scores = [score(i, j) for i, j in pairs]
    spread = max(scores) - min(scores)
    print(f"  RoPE is relative   : gap-2 score at positions {[p[0] for p in pairs]} "
          f"varies by {spread:.2e}")
    print(f"  RoPE norm preserved: {torch.allclose(apply_rope(qv, cos[7:8], sin[7:8]).norm(), qv.norm()):}")

    torch.manual_seed(0)
    slow = TinyGPT(Config(**PRESETS[args.preset], flash=False, dropout=0.0)).eval()
    torch.manual_seed(0)
    fast = TinyGPT(Config(**PRESETS[args.preset], flash=True, dropout=0.0)).eval()
    fast.load_state_dict(slow.state_dict())
    with torch.no_grad():
        gap = (slow(idx)[0] - fast(idx)[0]).abs().max().item()
    print(f"  flash == explicit  : max logit difference = {gap:.2e}")

    torch.manual_seed(0)
    prompt = torch.randint(0, cfg.vocab_size, (1, 48))
    t = time.perf_counter()
    fast = model.generate(prompt, max_new_tokens=32, temperature=0.0, top_k=None)
    t_fast = time.perf_counter() - t
    t = time.perf_counter()
    slow = model.generate(prompt, max_new_tokens=32, temperature=0.0, top_k=None,
                          use_cache=False)
    t_slow = time.perf_counter() - t
    print(f"  kv cache == no cache: {torch.equal(fast, slow)}   "
          f"({fast.shape[1] - prompt.shape[1]} tokens, {t_slow / t_fast:.1f}x faster)")

    model.train()
    out = model.generate(torch.zeros((1, 1), dtype=torch.long), max_new_tokens=8)
    print(f"  generate works    : {out.shape[1]} tokens produced")
    print(f"  train mode kept   : {model.training}  (generate must not leave eval on)")


if __name__ == "__main__":
    main()
