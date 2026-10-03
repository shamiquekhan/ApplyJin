"""Minimal held-out QLoRA experiment runner for local reproducibility."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def _load_cases(path: Path) -> list[str]:
    return [json.loads(line)["text"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _loss(model, tokenizer, text: str) -> torch.Tensor:
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
    tokens = {key: value.to(model.device) for key, value in tokens.items()}
    return model(**tokens, labels=tokens["input_ids"]).loss


def run(model_name: str, train_path: Path, heldout_path: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the QLoRA experiment")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        ),
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=4,
            lora_alpha=8,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.train()
    optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=1e-4)
    train_cases = _load_cases(train_path)
    heldout_cases = _load_cases(heldout_path)
    before = float(torch.stack([_loss(model, tokenizer, text).detach().float().cpu() for text in heldout_cases]).mean())
    started = time.perf_counter()
    optimizer.zero_grad()
    train_loss = sum(_loss(model, tokenizer, text) for text in train_cases) / len(train_cases)
    train_loss.backward()
    optimizer.step()
    elapsed_ms = (time.perf_counter() - started) * 1000
    model.eval()
    after = float(torch.stack([_loss(model, tokenizer, text).detach().float().cpu() for text in heldout_cases]).mean())
    return {
        "model": model_name,
        "method": "QLoRA-NF4",
        "train_cases": len(train_cases),
        "heldout_cases": len(heldout_cases),
        "train_loss": round(float(train_loss.detach().cpu()), 4),
        "heldout_loss_before": round(before, 4),
        "heldout_loss_after": round(after, 4),
        "heldout_loss_delta": round(after - before, 4),
        "train_step_ms": round(elapsed_ms, 2),
        "trainable_parameters": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small held-out QLoRA experiment")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--train", type=Path, default=Path("evaluation/datasets/lora_train.jsonl"))
    parser.add_argument("--heldout", type=Path, default=Path("evaluation/datasets/lora_heldout.jsonl"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.model, args.train, args.heldout)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()