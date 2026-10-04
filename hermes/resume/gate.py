"""Quality gate: provenance, claim support, page budget, requirement coverage.

Runs on the final rendered resume before it is shown or tracked. Violations
are blocking; coverage ratio and line counts are reported metrics (uncovered
requirements are legitimate gaps, not failures).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from hermes.inference.verification import ClaimReference, verify_claims
from hermes.resume.coverage import requirement_covers
from hermes.resume.ir import ResumeIR
from hermes.resume.planner import PAGE_LINE_BUDGET
from hermes.resume.requirements import Requirement


class GateReport(BaseModel):
    passed: bool = True
    violations: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    coverage_ratio: float = 1.0
    covered_requirements: int = 0
    total_requirements: int = 0
    estimated_lines: int = 0
    page_line_budget: int = PAGE_LINE_BUDGET
    over_budget: bool = False


def coverage_ratio(
    ir: ResumeIR, requirements: list[Requirement]
) -> tuple[float, int, int]:
    """(ratio, covered count, total count) weighted by importance."""
    if not requirements:
        return 1.0, 0, 0
    corpus = " ".join(b.text for b in ir.all_bullets())
    if ir.summary:
        corpus += " " + ir.summary.text
    corpus += " " + " ".join(
        name for names in ir.skills.categories.values() for name in names
    )
    total_weight = sum(r.importance for r in requirements)
    covered_weight = sum(
        r.importance for r in requirements if requirement_covers(r, corpus)
    )
    covered = sum(1 for r in requirements if requirement_covers(r, corpus))
    ratio = covered_weight / total_weight if total_weight else 1.0
    return round(ratio, 3), covered, len(requirements)


def gate(
    rendered_text: str,
    ir: ResumeIR,
    requirements: list[Requirement],
    evidence: list[tuple[str, str]],
    known_entities: Optional[dict[str, list[str]]] = None,
    over_budget: bool = False,
    estimated_lines: int = 0,
    page_line_budget: int = PAGE_LINE_BUDGET,
    references: Optional[list[ClaimReference]] = None,
) -> GateReport:
    """Validate the final resume. `references` avoids re-running claim
    verification when the caller already computed it."""
    violations: list[str] = []

    # 1. Provenance: every evidence id in the IR must exist upstream.
    pool_ids = {identifier for identifier, _ in evidence}
    unknown = sorted(set(ir.evidence_ids()) - pool_ids)
    if unknown:
        violations.append(f"Unknown evidence ids: {unknown[:5]}")

    # 2. Claim support against the evidence pool.
    if references is None:
        references = verify_claims(rendered_text, evidence, known_entities)
    unsupported = [r.claim for r in references if not r.supported]
    if unsupported:
        violations.append(f"Unsupported claims: {unsupported[:3]}")

    # 3. Page budget (planner already dropped what it could).
    if over_budget:
        violations.append(
            f"Resume exceeds the {page_line_budget}-line page budget "
            f"({estimated_lines} lines even after dropping bullets)"
        )

    ratio, covered, total = coverage_ratio(ir, requirements)
    return GateReport(
        passed=not violations,
        violations=violations,
        unsupported_claims=unsupported,
        coverage_ratio=ratio,
        covered_requirements=covered,
        total_requirements=total,
        estimated_lines=estimated_lines,
        page_line_budget=page_line_budget,
        over_budget=over_budget,
    )
