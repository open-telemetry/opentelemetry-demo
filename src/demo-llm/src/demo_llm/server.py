#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""OpenAI-compatible HTTP surface for the bundled small language model.

The Agent talks to an OpenAI-shaped endpoint, so serving the demo's own model
means implementing POST /v1/chat/completions and translating between two
formats: OpenAI chat messages, and the <|user|>/<|call|>/<|result|> transcript
the model was trained on.

Generation stops at <|result|>. The model was trained on transcripts that
contain tool output, so continuing past a tool call is exactly what it learned
to do - but in an agent loop that output would be invented. Stopping there hands
the tool call back so the Agent can run the real tool.
"""

import json
import os
import pathlib
import re
import time
import uuid

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import metrics, trace
from pydantic import BaseModel

from demo_llm.architecture import Config, TinyGPT
from demo_llm.tokenizer import ShopTokenizer

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
)
MARKERS = re.compile(
    r"(<\|assistant\|>|<\|call\|>|<\|result\|>|<\|user\|>|<\|end\|>)"
)

# gen_ai.provider.name identifies who serves the model, and this demo serves its
# own. Model, temperature and token counts are all upstream gen_ai conventions,
# so no demo specific attribute is defined for any of them.
PROVIDER = "demo-llm"

tracer = trace.get_tracer(__name__)


class ChatRequest(BaseModel):
    messages: list
    model: str | None = None
    tools: list | None = None
    temperature: float = 0.7
    top_k: int | None = 40
    max_tokens: int = 400
    stream: bool = False


def compact(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


class Adapter:
    def __init__(self, tok, conditioning):
        self.tok = tok
        self.sys_ids = {v: int(k) for k, v in conditioning["system_prompts"].items()}
        self.known_tools = sorted({n for ts in conditioning["tool_sets"] for n in ts})

    def encode(self, messages, tools):
        """OpenAI messages -> transcript prompt. Returns (text, uid_seen)."""
        system = next(
            (m.get("content") or "" for m in messages if m.get("role") == "system"), ""
        ).strip()
        # An unseen system prompt falls back to the one the model was trained on
        sys_id = self.sys_ids.get(system, 0)
        names = sorted(
            t["function"]["name"]
            for t in (tools or [])
            if t.get("function", {}).get("name")
        ) or self.known_tools

        parts = [f"<|sys:{sys_id}|>", "<|tools|>" + ",".join(names)]
        uid_seen = None
        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""
            if isinstance(content, list):
                content = "".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
            found = UUID_RE.search(content)
            if found and uid_seen is None:
                uid_seen = found.group()
            content = UUID_RE.sub("<|uid|>", content)

            if role == "system":
                continue
            if role == "user":
                parts.append("<|user|>" + content.strip())
            elif role == "tool":
                parts.append("<|result|>" + content.strip())
            elif role == "assistant":
                if content.strip():
                    parts.append("<|assistant|>" + content.strip())
                for call in m.get("tool_calls") or []:
                    fn = call.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    raw = compact(args)
                    if uid_seen is None:
                        found = UUID_RE.search(raw)
                        if found:
                            uid_seen = found.group()
                    parts.append(
                        "<|call|>" + fn.get("name", "") + UUID_RE.sub("<|uid|>", raw)
                    )
        return "".join(parts), uid_seen

    def split_call(self, segment):
        """'get_ads{"category":"telescopes"}' -> ('get_ads', {...})."""
        for name in sorted(self.known_tools, key=len, reverse=True):
            if segment.startswith(name):
                rest = segment[len(name):].strip()
                try:
                    return name, json.loads(rest)
                except json.JSONDecodeError:
                    return name, {}
        return None, {}

    def decode(self, text, uid_seen):
        """Generated transcript -> (content, tool_calls) in OpenAI shape."""
        if uid_seen:
            text = text.replace("<|uid|>", uid_seen)
        content, calls, current = [], [], None
        for piece in MARKERS.split(text):
            if piece in ("<|assistant|>", "<|call|>"):
                current = piece
                continue
            if piece in ("<|result|>", "<|user|>", "<|end|>"):
                break
            if current == "<|assistant|>" and piece.strip():
                content.append(piece.strip())
            elif current == "<|call|>" and piece.strip():
                name, args = self.split_call(piece.strip())
                if name:
                    calls.append({
                        "id": f"call_{uuid.uuid4().hex[:20]}",
                        "type": "function",
                        "function": {"name": name, "arguments": compact(args)},
                    })
        return "\n".join(content), calls


def load(checkpoint, artifacts_dir, device):
    artifacts = pathlib.Path(artifacts_dir)
    tok = ShopTokenizer.load(artifacts / "tokenizer.json")
    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    model = TinyGPT(Config(**ckpt["cfg"])).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    conditioning = json.loads((artifacts / "conditioning.json").read_text())
    return model, tok, Adapter(tok, conditioning), ckpt


def build_app(model, tok, adapter, device, model_name, max_retries=3):
    app = FastAPI(title="demo-llm")
    stop_ids = [
        tok.atom_to_id[m]
        for m in ("<|result|>", "<|end|>", "<|user|>")
        if m in tok.atom_to_id
    ]
    stats = {"requests": 0, "resampled": 0, "dropped_calls": 0}

    meter = metrics.get_meter(__name__)
    request_duration = meter.create_histogram(
        "gen_ai.server.request.duration",
        unit="s",
        description="Generative AI server request duration such as "
                    "time-to-last byte or last output token.",
    )
    time_to_first_token = meter.create_histogram(
        "gen_ai.server.time_to_first_token",
        unit="s",
        description="Time to generate first token for successful responses.",
    )
    time_per_output_token = meter.create_histogram(
        "gen_ai.server.time_per_output_token",
        unit="s",
        description="Time per output token generated after the first token "
                    "for successful responses.",
    )
    resamples = meter.create_counter(
        "demo.llm.resamples",
        unit="{resample}",
        description="Generations thrown away and retried because the model "
                    "returned nothing usable.",
    )
    dropped_tool_calls = meter.create_counter(
        "demo.llm.dropped_tool_calls",
        unit="{tool_call}",
        description="Tool calls removed from the response because the Agent "
                    "could not have executed them.",
    )

    def offered_names(req):
        return {
            t["function"]["name"]
            for t in (req.tools or [])
            if t.get("function", {}).get("name")
        } or set(adapter.known_tools)

    def invalid(calls, allowed):
        """A call is bad if it names a tool the caller never offered, or if its
        arguments did not survive as JSON. Both happen when the model drifts off
        the trajectories it learned.
        """
        bad = []
        for c in calls:
            fn = c["function"]
            if fn["name"] not in allowed:
                bad.append((fn["name"], "not_offered"))
                continue
            try:
                json.loads(fn["arguments"])
            except json.JSONDecodeError:
                bad.append((fn["name"], "unparseable_arguments"))
        return bad

    def run(req):
        prompt, uid_seen = adapter.encode(req.messages, req.tools)
        ids = tok.encode(prompt)
        room = model.cfg.context - req.max_tokens
        truncated = len(ids) > room
        if truncated:
            ids = ids[-room:]
        allowed = offered_names(req)
        stats["requests"] += 1

        content, calls, n_gen, bad, tries = "", [], 0, [], 0
        ttft, decode = None, None
        for attempt in range(max_retries + 1):
            tries = attempt + 1
            with tracer.start_as_current_span("generate") as span:
                first_at = None

                def on_first_token():
                    nonlocal first_at
                    first_at = time.perf_counter()

                started = time.perf_counter()
                out = model.generate(
                    torch.tensor([ids], device=device),
                    max_new_tokens=req.max_tokens,
                    temperature=req.temperature,
                    top_k=req.top_k,
                    stop_id=stop_ids,
                    on_first_token=on_first_token,
                )
                finished = time.perf_counter()
                n_gen = out.shape[1] - len(ids)
                content, calls = adapter.decode(
                    tok.decode(out[0].tolist()[len(ids):]), uid_seen
                )
                bad = invalid(calls, allowed)

                # The prompt forward pass is everything up to the first sampled
                # token; the rest is one pass per token, served from the KV
                # cache. Splitting them is what makes a slow request readable.
                ttft = None if first_at is None else first_at - started
                decode = None if first_at is None else finished - first_at
                span.set_attribute("demo.llm.sample_attempt", tries)
                span.set_attribute("gen_ai.usage.output_tokens", n_gen)
                if ttft is not None:
                    span.set_attribute("demo.llm.time_to_first_token", ttft)
                if bad:
                    span.set_attribute(
                        "demo.llm.tool_call_rejection_reasons",
                        sorted({reason for _, reason in bad}),
                    )

            if not bad and (content.strip() or calls):
                break
            if attempt < max_retries:
                stats["resampled"] += 1
                resamples.add(1, {"gen_ai.request.model": model_name})

        if bad:
            # Returning a call the Agent cannot execute is worse than returning
            # none.
            dropped = {n for n, _ in bad}
            calls = [c for c in calls if c["function"]["name"] not in dropped]
            stats["dropped_calls"] += len(bad)
            for _, reason in bad:
                dropped_tool_calls.add(1, {
                    "gen_ai.request.model": model_name,
                    "demo.llm.tool_call_rejection_reason": reason,
                })
        return {
            "content": content,
            "calls": calls,
            "prompt_tokens": len(ids),
            "output_tokens": n_gen,
            "attempts": tries,
            "dropped": len(bad),
            "truncated": truncated,
            "ttft": ttft,
            "decode": decode,
        }

    def envelope(content, calls, n_prompt, n_gen):
        message = {"role": "assistant", "content": content or None}
        if calls:
            message["tool_calls"] = calls
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if calls else "stop",
                "logprobs": None,
            }],
            "usage": {
                "prompt_tokens": n_prompt,
                "completion_tokens": n_gen,
                "total_tokens": n_prompt + n_gen,
            },
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "model": model_name,
            "params": model.param_breakdown()["TOTAL"],
            **stats,
        }

    @app.get("/v1/models")
    def models():
        return {
            "object": "list",
            "data": [{
                "id": model_name,
                "object": "model",
                "created": 0,
                "owned_by": "opentelemetry-demo",
            }],
        }

    @app.post("/v1/chat/completions")
    def completions(req: ChatRequest):
        if not req.messages:
            raise HTTPException(400, "messages must not be empty")

        # The same attributes identify the operation on every gen_ai metric, so
        # a span and its metrics can be filtered the same way.
        common = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": PROVIDER,
            "gen_ai.request.model": req.model or model_name,
            "gen_ai.response.model": model_name,
        }
        started = time.perf_counter()
        with tracer.start_as_current_span(
            f"chat {model_name}", kind=trace.SpanKind.SERVER
        ) as span:
            try:
                out = run(req)
            except Exception as exc:
                request_duration.record(
                    time.perf_counter() - started,
                    dict(common, **{"error.type": type(exc).__qualname__}),
                )
                raise

            calls, n_prompt = out["calls"], out["prompt_tokens"]
            n_gen = out["output_tokens"]
            body = envelope(out["content"], calls, n_prompt, n_gen)
            elapsed = time.perf_counter() - started

            span.set_attributes(common)
            span.set_attribute("gen_ai.request.temperature", req.temperature)
            span.set_attribute("gen_ai.request.max_tokens", req.max_tokens)
            if req.top_k is not None:
                span.set_attribute("gen_ai.request.top_k", req.top_k)
            span.set_attribute("gen_ai.response.id", body["id"])
            span.set_attribute("gen_ai.usage.input_tokens", n_prompt)
            span.set_attribute("gen_ai.usage.output_tokens", n_gen)
            span.set_attribute(
                "gen_ai.response.finish_reasons",
                ["tool_calls"] if calls else ["stop"],
            )
            span.set_attribute("demo.llm.sample_attempts", out["attempts"])
            span.set_attribute("demo.llm.dropped_tool_calls", out["dropped"])
            span.set_attribute("demo.llm.prompt_truncated", out["truncated"])

            # Token usage is not recorded here: the Agent already reports
            # gen_ai.client.token.usage for the same call, and it is the only
            # caller, so a server side copy would only double count.
            request_duration.record(elapsed, common)
            if out["ttft"] is not None:
                time_to_first_token.record(out["ttft"], common)
            if out["decode"] is not None and n_gen > 1:
                time_per_output_token.record(out["decode"] / (n_gen - 1), common)

        if not req.stream:
            return body
        def sse():
            head = {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": body["created"],
                "model": model_name,
            }
            yield f'data: {json.dumps(dict(head, choices=[{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]))}\n\n'
            delta = {"content": body["choices"][0]["message"]["content"]}
            if calls:
                delta["tool_calls"] = [dict(c, index=i) for i, c in enumerate(calls)]
            yield f'data: {json.dumps(dict(head, choices=[{"index": 0, "delta": delta, "finish_reason": None}]))}\n\n'
            fin = body["choices"][0]["finish_reason"]
            yield f'data: {json.dumps(dict(head, choices=[{"index": 0, "delta": {}, "finish_reason": fin}]))}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    return app


def create_app():
    """Build the app from environment configuration."""
    artifacts = os.getenv("DEMO_LLM_ARTIFACTS", "artifacts")
    checkpoint = os.getenv("DEMO_LLM_CHECKPOINT", f"{artifacts}/model.pt")
    device = torch.device(os.getenv("DEMO_LLM_DEVICE", "cpu"))
    model_name = os.getenv("DEMO_LLM_MODEL_NAME", "demo-llm")
    retries = int(os.getenv("DEMO_LLM_MAX_RETRIES", "3"))

    torch.set_num_threads(int(os.getenv("DEMO_LLM_THREADS", "2")))
    model, tok, adapter, ckpt = load(checkpoint, artifacts, device)
    print(
        f"demo-llm: loaded {checkpoint} "
        f"(step {ckpt.get('step', '?')}, val {ckpt.get('val_loss', float('nan')):.4f}, "
        f"{model.param_breakdown()['TOTAL']:,} params)",
        flush=True,
    )
    return build_app(model, tok, adapter, device, model_name, retries)
