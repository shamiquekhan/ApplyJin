"""Benchmark an OpenAI-compatible vLLM server without paid APIs.

Example:
  python -m evaluation.benchmarks.vllm_benchmark --requests 8 --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from urllib.request import urlopen

from hermes.inference.vllm_client import VLLMProvider


async def _one(provider: VLLMProvider, prompt: str, max_tokens: int) -> dict[str, float | int | str]:
    started = time.perf_counter()
    first_token: float | None = None
    tokens = 0
    try:
        async for chunk in provider.stream(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        ):
            if first_token is None:
                first_token = time.perf_counter()
            tokens += max(1, len(chunk.split()))
        finished = time.perf_counter()
        total_ms = (finished - started) * 1000
        ttft_ms = ((first_token or finished) - started) * 1000
        decode_ms = max(0.0, total_ms - ttft_ms)
        return {
            "status": "ok",
            "ttft_ms": round(ttft_ms, 2),
            "latency_ms": round(total_ms, 2),
            "tpot_ms": round(decode_ms / tokens, 2) if tokens else 0.0,
            "tokens": tokens,
        }
    except Exception as exc:  # noqa: BLE001 - failures are benchmark results
        return {"status": "error", "error": type(exc).__name__, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * percentage / 100))]


def summarize(results: list[dict[str, float | int | str]], elapsed_seconds: float) -> dict[str, float | int]:
    successful = [result for result in results if result["status"] == "ok"]
    latencies = [float(result["latency_ms"]) for result in successful]
    ttft = [float(result["ttft_ms"]) for result in successful]
    tpot = [float(result["tpot_ms"]) for result in successful]
    tokens = sum(int(result["tokens"]) for result in successful)
    return {
        "requests": len(results),
        "successful": len(successful),
        "failures": len(results) - len(successful),
        "failure_rate": round((len(results) - len(successful)) / len(results), 4) if results else 0.0,
        "ttft_p50_ms": round(percentile(ttft, 50), 2),
        "ttft_p95_ms": round(percentile(ttft, 95), 2),
        "tpot_p50_ms": round(percentile(tpot, 50), 2),
        "tpot_p95_ms": round(percentile(tpot, 95), 2),
        "latency_p50_ms": round(percentile(latencies, 50), 2),
        "latency_p95_ms": round(percentile(latencies, 95), 2),
        "latency_p99_ms": round(percentile(latencies, 99), 2),
        "tokens_per_second": round(tokens / elapsed_seconds, 2) if elapsed_seconds else 0.0,
        "requests_per_second": round(len(successful) / elapsed_seconds, 2) if elapsed_seconds else 0.0,
    }


def server_metrics(base_url: str) -> str:
    """Fetch raw vLLM Prometheus metrics when the server exposes them."""
    metrics_url = base_url.rstrip("/").removesuffix("/v1") + "/metrics"
    try:
        with urlopen(metrics_url, timeout=3) as response:  # noqa: S310 - configured local URL
            return response.read().decode("utf-8")
    except Exception:
        return ""


async def run(requests: int, concurrency: int, max_tokens: int) -> dict:
    provider = VLLMProvider()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def limited(index: int):
        async with semaphore:
            return await _one(provider, f"Benchmark request {index}: respond briefly.", max_tokens)

    started = time.perf_counter()
    results = await asyncio.gather(*(limited(index) for index in range(requests)))
    elapsed = time.perf_counter() - started
    report = summarize(results, elapsed)
    report["server_metrics_available"] = bool(server_metrics(provider.base_url))
    report["model"] = provider.model
    report["concurrency"] = concurrency
    report["max_tokens"] = max_tokens
    report["results"] = results
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark a local vLLM server")
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = asyncio.run(run(args.requests, args.concurrency, args.max_tokens))
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()