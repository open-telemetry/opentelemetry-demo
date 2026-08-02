#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import pathlib
import re
from collections import Counter, defaultdict

STRUCTURAL = ["<|user|>", "<|assistant|>", "<|call|>", "<|result|>", "<|end|>",
              "<|uid|>", "<|tools|>"]


def discover_conditioning_atoms(data_dir, text):
    """<|sys:k|> markers and tool names, read from the Block 1 sidecar so the two
    blocks cannot drift apart."""
    path = pathlib.Path(data_dir) / "conditioning.json"
    if not path.exists():
        return sorted(set(re.findall(r"<\|sys:\d+\|>", text)))
    d = json.loads(path.read_text())
    sys_tokens = [f"<|sys:{k}|>" for k in d["system_prompts"]]
    tools = sorted({name for ts in d["tool_sets"] for name in ts})
    return sys_tokens + tools

PRETOK = re.compile(r"""'(?:s|t|re|ve|m|ll|d)| ?[A-Za-z]+| ?[0-9]{1,3}| ?[^\sA-Za-z0-9]+|\s+""")


def discover_product_ids(text, min_count=5):
    """Catalogue ids are fixed 10-char uppercase alphanumerics."""
    counts = Counter(re.findall(r"\b[A-Z0-9]{10}\b", text))
    return sorted(t for t, n in counts.items() if n >= min_count)


def pretokenize(text, atoms):
    """Yield (is_atom, string) chunks, never splitting an atom."""
    if not atoms:
        for m in PRETOK.finditer(text):
            yield False, m.group()
        return
    pattern = re.compile("|".join(re.escape(a) for a in sorted(atoms, key=len, reverse=True)))
    pos = 0
    for m in pattern.finditer(text):
        for pm in PRETOK.finditer(text[pos:m.start()]):
            yield False, pm.group()
        yield True, m.group()
        pos = m.end()
    for pm in PRETOK.finditer(text[pos:]):
        yield False, pm.group()


def _pairs(symbols):
    return zip(symbols, symbols[1:])


def train_bpe(word_freqs, num_merges, first_id):
    words = [list(w) for w in word_freqs]
    freqs = list(word_freqs.values())

    counts = Counter()
    where = defaultdict(set)

    def contribute(i, sign):
        f = freqs[i] * sign
        for p in _pairs(words[i]):
            counts[p] += f
            if sign > 0:
                where[p].add(i)
            elif counts[p] <= 0:
                counts.pop(p, None)
        if sign < 0:
            for p in set(_pairs(words[i])):
                where[p].discard(i)

    for i in range(len(words)):
        contribute(i, +1)

    merges = []
    for step in range(num_merges):
        if not counts:
            break
        best = max(counts, key=lambda p: (counts[p], p))
        if counts[best] < 2:
            break
        new_id = first_id + step
        a, b = best
        for i in list(where.get(best, ())):
            contribute(i, -1)
            sym, out, j = words[i], [], 0
            while j < len(sym):
                if j < len(sym) - 1 and sym[j] == a and sym[j + 1] == b:
                    out.append(new_id)
                    j += 2
                else:
                    out.append(sym[j])
                    j += 1
            words[i] = out
            contribute(i, +1)
        merges.append(best)
    return merges


class ShopTokenizer:
    def __init__(self, atoms, merges):
        self.atoms = list(atoms)
        self.merges = [tuple(m) for m in merges]
        self.atom_base = 256
        self.merge_base = 256 + len(self.atoms)
        self.atom_to_id = {a: self.atom_base + i for i, a in enumerate(self.atoms)}
        self.rank = {p: i for i, p in enumerate(self.merges)}
        self.vocab_size = self.merge_base + len(self.merges)

        self.bytes_of = {i: bytes([i]) for i in range(256)}
        for a, i in self.atom_to_id.items():
            self.bytes_of[i] = a.encode()
        for k, (a, b) in enumerate(self.merges):
            self.bytes_of[self.merge_base + k] = self.bytes_of[a] + self.bytes_of[b]

    def _bpe(self, chunk):
        ids = list(chunk.encode())
        while len(ids) >= 2:
            best, best_rank = None, None
            for p in _pairs(ids):
                r = self.rank.get(p)
                if r is not None and (best_rank is None or r < best_rank):
                    best, best_rank = p, r
            if best is None:
                break
            a, b = best
            new_id = self.merge_base + best_rank
            out, j = [], 0
            while j < len(ids):
                if j < len(ids) - 1 and ids[j] == a and ids[j + 1] == b:
                    out.append(new_id)
                    j += 2
                else:
                    out.append(ids[j])
                    j += 1
            ids = out
        return ids

    def encode(self, text):
        ids = []
        for is_atom, chunk in pretokenize(text, self.atoms):
            if is_atom:
                ids.append(self.atom_to_id[chunk])
            else:
                ids.extend(self._bpe(chunk))
        return ids

    def decode(self, ids):
        return b"".join(self.bytes_of[i] for i in ids).decode("utf-8", errors="replace")

    def save(self, path):
        pathlib.Path(path).write_text(json.dumps(
            {"atoms": self.atoms, "merges": [list(m) for m in self.merges]}))

    @classmethod
    def load(cls, path):
        d = json.loads(pathlib.Path(path).read_text())
        return cls(d["atoms"], d["merges"])
