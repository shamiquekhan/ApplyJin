"""Budgeted context assembly for retrieval-augmented generation."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_CONTEXT_BUDGET = {"job": 2500, "candidate_evidence": 4000, "instructions": 1200, "output": 1500}


def _truncate(text: str, budget: int) -> str:
    return text[: max(0, budget)]


@dataclass
class ContextPackage:
    job: str
    candidate_evidence: list[str]
    instructions: str
    output_budget: int
    retrieved_chunks: int
    discarded_chunks: int
    input_characters: int
    budget_characters: int
    metadata: dict[str, int] = field(default_factory=dict)

    @property
    def context_utilization(self) -> float:
        return round(min(1.0, self.input_characters / self.budget_characters), 4) if self.budget_characters else 0.0

    def as_prompt(self) -> str:
        evidence = "\n".join(f"- {item}" for item in self.candidate_evidence)
        return ("<UNTRUSTED_JOB_DESCRIPTION>\n" f"{self.job}\n" "</UNTRUSTED_JOB_DESCRIPTION>\n\n"
                "<VERIFIED_CANDIDATE_EVIDENCE>\n" f"{evidence}\n" "</VERIFIED_CANDIDATE_EVIDENCE>\n\n" f"{self.instructions}")


def build_context(job: str, evidence: list[str], instructions: str, budgets: dict[str, int] | None = None) -> ContextPackage:
    """Assemble bounded, explicitly delimited context in retrieval rank order."""
    budget = {**DEFAULT_CONTEXT_BUDGET, **(budgets or {})}
    selected: list[str] = []
    used = 0
    for item in evidence:
        remaining = budget["candidate_evidence"] - used
        if remaining <= 0:
            break
        clipped = _truncate(item, remaining)
        if clipped:
            selected.append(clipped)
            used += len(clipped)
    job_text = _truncate(job, budget["job"])
    instruction_text = _truncate(instructions, budget["instructions"])
    input_characters = len(job_text) + used + len(instruction_text)
    return ContextPackage(job_text, selected, instruction_text, budget["output"], len(evidence), max(0, len(evidence) - len(selected)), input_characters, budget["job"] + budget["candidate_evidence"] + budget["instructions"], {"input_characters": input_characters, "output_budget": budget["output"]})
