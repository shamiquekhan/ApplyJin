"""Phase 4+5: deterministic renderer, constrained composer, quality gate."""

from __future__ import annotations

import json

from hermes.resume.composer import compose_ir
from hermes.resume.gate import coverage_ratio, gate
from hermes.resume.planner import ir_from_selection, plan_resume
from hermes.resume.render import render_markdown
from hermes.resume.requirements import make_requirement

SNAPSHOT = {
    "profile": {
        "full_name": "Shamique Khan",
        "headline": "AI Engineer",
        "summary": "Focused on RAG pipelines and agents",
        "email": "a@b.co",
        "location": "India",
    },
    "experiences": [
        {"id": 1, "title": "AI Engineer Intern", "organization": "Suproc",
         "start_date": "Jul 2026", "end_date": "Present",
         "bullets": ["Built XGBoost ranking model 15%"]},
    ],
    "projects": [
        {"id": 4, "name": "RAG Agent", "tech": "Python, FAISS",
         "bullets": ["Built RAG pipeline with Python"]},
    ],
    "education": [
        {"degree": "B.Tech CSE", "institution": "VIT",
         "start_date": "2025", "end_date": "2029", "details": "AI & ML"},
    ],
    "certifications": [
        {"name": "Oracle OCI Gen AI", "issuer": "Oracle", "year": "2026"},
    ],
    "skills": {"ml": ["XGBoost"], "core": ["Python"]},
}

REQUIREMENTS = [
    make_requirement("Experience with Python"),
    make_requirement("Experience with XGBoost"),
    make_requirement("Experience with Kubernetes"),  # no evidence
]


def _plan():
    ir = ir_from_selection(
        SNAPSHOT, [1], [4], requirements=REQUIREMENTS,
        skills=["Python", "XGBoost"],
    )
    return plan_resume(ir, REQUIREMENTS)


class _Response:
    def __init__(self, text: str, model: str = "fake"):
        self.text = text
        self.model = model


class _Router:
    def __init__(self, text: str, model: str = "fake"):
        self.text = text
        self.model = model
        self.calls = 0

    def complete(self, prompt, system="", task="generation", context_length=0):
        self.calls += 1
        return _Response(self.text, self.model)


# ---------------------------------------------------------------- render


class TestRender:
    def test_ats_sections_and_pipe_format(self):
        md = render_markdown(_plan().ir)
        assert md.startswith("# Shamique Khan")
        assert "India | a@b.co" in md
        assert "## Summary" in md
        assert "### AI Engineer Intern | Suproc | Jul 2026 - Present" in md
        assert "### RAG Agent — Python, FAISS" in md
        assert "## Skills\nPython, XGBoost" in md
        assert "- B.Tech CSE | VIT | 2029" in md
        assert "- Oracle OCI Gen AI · Oracle · 2026" in md

    def test_deterministic(self):
        plan = _plan()
        assert render_markdown(plan.ir) == render_markdown(plan.ir)

    def test_bullets_render_with_dash_prefix(self):
        md = render_markdown(_plan().ir)
        assert "- Built XGBoost ranking model 15%" in md


# ---------------------------------------------------------------- composer


class TestCompose:
    def _payload(self, mutate) -> str:
        payload = _plan().ir.model_dump()
        mutate(payload)
        return json.dumps(payload)

    def test_valid_edit_preserves_provenance(self):
        def mutate(p):
            p["experience"][0]["bullets"][0]["text"] = (
                "Cut ranking errors 15% with an XGBoost model in production"
            )

        router = _Router(self._payload(mutate))
        edited, model = compose_ir(_plan().ir, "JD", REQUIREMENTS, router)
        assert edited is not None
        assert model == "fake"
        bullet = edited.experience[0].bullets[0]
        assert "Cut ranking errors" in bullet.text
        original = _plan().ir.experience[0].bullets[0]
        assert bullet.evidence_ids == original.evidence_ids
        assert bullet.requirement_ids == original.requirement_ids
        assert bullet.importance == original.importance
        assert router.calls == 1

    def test_fenced_json_accepted(self):
        def mutate(p):
            p["summary"]["text"] = "RAG-focused AI engineer"

        payload = "```json\n" + self._payload(mutate) + "\n```"
        edited, _ = compose_ir(_plan().ir, "JD", REQUIREMENTS, _Router(payload))
        assert edited is not None
        assert edited.summary.text == "RAG-focused AI engineer"

    def test_summary_as_plain_string_coerced(self):
        # Gemini habit: emit summary as a bare string instead of {text}.
        payload = _plan().ir.model_dump()
        payload["summary"] = "AI engineer focused on retrieval pipelines"
        edited, _ = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(json.dumps(payload))
        )
        assert edited is not None
        assert edited.summary.text == "AI engineer focused on retrieval pipelines"

    def test_non_json_rejected(self):
        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS,
            _Router("# Shamique Khan\n\nNot JSON at all"),
        )
        assert edited is None
        assert reason == "compose-invalid"

    def test_invented_evidence_id_rejected(self):
        def mutate(p):
            p["experience"][0]["bullets"][0]["evidence_ids"] = ["exp-99-b7"]

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_changed_date_rejected(self):
        def mutate(p):
            p["experience"][0]["end_date"] = "Present Remote, North America"

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_changed_title_rejected(self):
        def mutate(p):
            p["experience"][0]["title"] = "Senior AI Engineer"

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_changed_header_name_rejected(self):
        def mutate(p):
            p["header"]["name"] = "Sam Khan"

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_changed_education_rejected(self):
        def mutate(p):
            if p["education"]:
                p["education"][0]["degree"] = "PhD"
            else:
                p["education"].append(
                    {"degree": "PhD", "institution": "X",
                     "start_date": "", "end_date": "", "details": ""}
                )

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_invented_skill_rejected(self):
        def mutate(p):
            first = next(iter(p["skills"]["categories"]))
            p["skills"]["categories"][first].append("Quantum Computing")

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_reordered_skills_accepted(self):
        def mutate(p):
            cats = p["skills"]["categories"]
            if len(cats) >= 2:
                keys = list(cats)
                cats[keys[0]], cats[keys[1]] = cats[keys[1]], cats[keys[0]]

        edited, _ = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is not None

    def test_added_bullet_rejected(self):
        def mutate(p):
            p["experience"][0]["bullets"].append(dict(
                p["experience"][0]["bullets"][0],
                text="Invented extra bullet",
            ))

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_changed_importance_rejected(self):
        def mutate(p):
            p["experience"][0]["bullets"][0]["importance"] = 0.01

        edited, reason = compose_ir(
            _plan().ir, "JD", REQUIREMENTS, _Router(self._payload(mutate))
        )
        assert edited is None
        assert reason == "compose-provenance"

    def test_no_router(self):
        edited, reason = compose_ir(_plan().ir, "JD", REQUIREMENTS, None)
        assert edited is None
        assert reason == "no-router"


# ---------------------------------------------------------------- gate


class TestGate:
    def _evidence(self, rendered: str):
        plan = _plan()
        evidence = [
            (eid, bullet.text)
            for bullet in plan.ir.all_bullets()
            for eid in bullet.evidence_ids
        ]
        evidence.append(("selection", rendered))
        return evidence

    def test_clean_resume_passes_with_gap_ratio(self):
        plan = _plan()
        rendered = render_markdown(plan.ir)
        report = gate(
            rendered, plan.ir, REQUIREMENTS, self._evidence(rendered),
            {"SKILL": ["Python"]},
            estimated_lines=plan.estimated_lines,
            page_line_budget=plan.page_line_budget,
        )
        assert report.passed
        assert report.violations == []
        assert report.total_requirements == 3
        assert report.covered_requirements == 2  # Kubernetes is a real gap
        assert report.coverage_ratio == 0.667

    def test_unknown_evidence_id_blocks(self):
        plan = _plan()
        rendered = render_markdown(plan.ir)
        evidence = self._evidence(rendered)  # built BEFORE tampering
        plan.ir.experience[0].bullets[0].evidence_ids = ["exp-99-b0"]
        report = gate(rendered, plan.ir, REQUIREMENTS, evidence)
        assert not report.passed
        assert any("Unknown evidence ids" in v for v in report.violations)

    def test_unsupported_claim_blocks(self):
        plan = _plan()
        clean = render_markdown(plan.ir)
        evidence = self._evidence(clean)  # the fabrication is NOT evidence
        report = gate(
            clean + "- Led a team of fifty engineers across three continents "
            "and shipped the platform worldwide\n",
            plan.ir, REQUIREMENTS, evidence,
        )
        assert not report.passed
        assert report.unsupported_claims

    def test_over_budget_blocks(self):
        plan = _plan()
        rendered = render_markdown(plan.ir)
        report = gate(
            rendered, plan.ir, REQUIREMENTS, self._evidence(rendered),
            over_budget=True, estimated_lines=60, page_line_budget=46,
        )
        assert not report.passed
        assert any("page budget" in v for v in report.violations)

    def test_no_requirements_full_coverage(self):
        assert coverage_ratio(_plan().ir, []) == (1.0, 0, 0)
