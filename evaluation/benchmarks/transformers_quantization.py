"""Compare FP16 and 4-bit NF4 Transformers inference locally."""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def _prompt(tokenizer, text: str):
    messages = [{"role": "user", "content": text}]
    if hasattr(tokenizer, "apply_chat_template"):
        encoded = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        )
        return encoded.input_ids if hasattr(encoded, "input_ids") else encoded
    return tokenizer(text, return_tensors="pt").input_ids


def benchmark_variant(model_name: str, quantized: bool, max_new_tokens: int = 32) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the local quantization benchmark")
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    quantization_config = None
    if quantized:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    load_started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype=torch.float16,
        quantization_config=quantization_config,
    )
    load_ms = (time.perf_counter() - load_started) * 1000
    inputs = _prompt(tokenizer, "Explain retrieval augmented generation in one sentence.")
    inputs = inputs.to(model.device)
    with torch.inference_mode():
        started = time.perf_counter()
        output = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
        latency_ms = (time.perf_counter() - started) * 1000
    generated_tokens = int(output.shape[-1] - inputs.shape[-1])
    peak_memory_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
    result = {
        "variant": "nf4-4bit" if quantized else "fp16",
        "model": model_name,
        "load_ms": round(load_ms, 2),
        "latency_ms": round(latency_ms, 2),
        "generated_tokens": generated_tokens,
        "tokens_per_second": round(generated_tokens / (latency_ms / 1000), 2) if latency_ms else 0.0,
        "peak_gpu_memory_mb": round(peak_memory_mb, 2),
        "text": tokenizer.decode(output[0][inputs.shape[-1]:], skip_special_tokens=True),
    }
    del model, tokenizer, inputs, output
    gc.collect()
    torch.cuda.empty_cache()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare FP16 and NF4 4-bit inference")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "model": args.model,
        "variants": [
            benchmark_variant(args.model, False, args.max_new_tokens),
            benchmark_variant(args.model, True, args.max_new_tokens),
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()