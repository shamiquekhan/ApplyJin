"""Budgeted context assembly for retrieval-augmented generation.

All budgets are expressed in model tokens; selection, truncation, and
reporting share one ``TokenCounter`` so ``ContextPackage.input_tokens``
means the same thing as the model context window it is compared against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from applyjin.inference.tokens import ApproximateTokenCounter, TokenCounter, estimate_tokens

__all__ = ["DEFAULT_CONTEXT_BUDGET", "ContextPackage", "build_context", "estimate_tokens"]

# Section budgets in tokens (jobs, evidence, instructions, reserved output).
DEFAULT_CONTEXT_BUDGET = {"job": 2500, "candidate_evidence": 4000, "instructions": 1200, "output": 1500}


@dataclass
class ContextPackage:
    job: str
    candidate_evidence: list[str]
    instructions: str
    output_budget: int
    retrieved_chunks: int
    discarded_chunks: int
    input_tokens: int
    budget_tokens: int
    metadata: dict[str, int] = field(default_factory=dict)

    @property
    def input_characters(self) -> int:
        return len(self.job) + sum(len(item) for item in self.candidate_evidence) + len(self.instructions)

    @property
    def context_utilization(self) -> float:
        return round(min(1.0, self.input_tokens / self.budget_tokens), 4) if self.budget_tokens else 0.0

    def as_prompt(self) -> str:
        evidence = "\n".join(f"- {item}" for item in self.candidate_evidence)
        return ("<UNTRUSTED_JOB_DESCRIPTION>\n" f"{self.job}\n" "</UNTRUSTED_JOB_DESCRIPTION>\n\n"
                "<VERIFIED_CANDIDATE_EVIDENCE>\n" f"{evidence}\n" "</VERIFIED_CANDIDATE_EVIDENCE>\n\n" f"{self.instructions}")


def build_context(
    job: str,
    evidence: list[str],
    instructions: str,
    budgets: dict[str, int] | None = None,
    counter: TokenCounter | None = None,
) -> ContextPackage:
    """Assemble bounded, explicitly delimited context in retrieval rank order."""
    counter = counter or ApproximateTokenCounter()
    budget = {**DEFAULT_CONTEXT_BUDGET, **(budgets or {})}
    selected: list[str] = []
    used = 0
    for item in evidence:
        remaining = budget["candidate_evidence"] - used
        if remaining <= 0:
            break
        clipped = counter.truncate(item, remaining)
        if clipped:
            selected.append(clipped)
            used += counter.count(clipped)
    job_text = counter.truncate(job, budget["job"])
    instruction_text = counter.truncate(instructions, budget["instructions"])
    input_tokens = counter.count(job_text) + used + counter.count(instruction_text)
    budget_tokens = budget["job"] + budget["candidate_evidence"] + budget["instructions"]
    return ContextPackage(
        job=job_text,
        candidate_evidence=selected,
        instructions=instruction_text,
        output_budget=budget["output"],
        retrieved_chunks=len(evidence),
        discarded_chunks=max(0, len(evidence) - len(selected)),
        input_tokens=input_tokens,
        budget_tokens=budget_tokens,
        metadata={
            "input_tokens": input_tokens,
            "budget_tokens": budget_tokens,
            "output_budget": budget["output"],
        },
    )
