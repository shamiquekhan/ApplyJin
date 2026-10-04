"""Resume Engine Phase 1: requirement schema/normalization/importance,
evidence extraction/strength, and the ResumeIR."""

from __future__ import annotations

import pytest

from hermes.resume import (
    Evidence,
    HeaderIR,
    ImportanceWeights,
    ResumeBullet,
    ResumeIR,
    estimate_lines,
    estimate_strength,
    evidence_from_snapshot,
    extract_metrics,
    make_requirement,
    normalize_skill,
)
from hermes.resume.requirements import compute_importance


# ---------------------------------------------------------------- requirements


class TestNormalizeSkill:
    def test_alias_surface_forms(self):
        assert normalize_skill("Retrieval-Augmented Generation") == "rag"
        assert normalize_skill("retrieval augmented generation") == "rag"
        assert normalize_skill("  LLMs  ") == "llm"
        assert normalize_skill("Large Language Models") == "llm"

    def test_case_and_punctuation_cleanup(self):
        assert normalize_skill("PyTorch") == "pytorch"
        assert normalize_skill("Node.js ") == "nodejs"
        assert normalize_skill("CI/CD") == "cicd"
        assert normalize_skill("K8s") == "kubernetes"

    def test_unknown_terms_pass_through(self):
        assert normalize_skill("Vector Search") == "vector search"


class TestMakeRequirement:
    def test_deterministic_ids_and_normalized_aliases(self):
        a = make_requirement("Experience with retrieval-augmented generation")
        b = make_requirement("Experience with retrieval-augmented generation")
        c = make_requirement("Experience with FastAPI")
        assert a.id == b.id
        assert a.id != c.id
        assert a.normalized == "rag"

    def test_evidence_required_defaults_from_mandatory(self):
        assert make_requirement("Must have Python", mandatory=True).evidence_required
        assert not make_requirement("Familiarity with Docker").evidence_required

    def test_aliases_normalized(self):
        req = make_requirement("Build RAG systems", aliases=["Retrieval Augmented Generation"])
        assert req.aliases == ["rag"]


class TestImportance:
    def test_explicitness_tiers_match_plan_examples(self):
        assert compute_importance(make_requirement("Must have Python")) == pytest.approx(1.0)
        assert compute_importance(make_requirement("Experience with RAG")) == pytest.approx(0.95)
        assert compute_importance(make_requirement("Familiarity with Docker")) == pytest.approx(0.65)
        assert compute_importance(make_requirement("Knowledge of AWS")) == pytest.approx(0.55)

    def test_soft_skills_capped(self):
        req = make_requirement("Excellent communication", category="SOFT_SKILL")
        assert compute_importance(req) == pytest.approx(0.25)

    def test_repetition_and_responsibility_boosts_are_capped(self):
        req = make_requirement("Familiarity with Docker")
        boosted = compute_importance(req, repetitions=4)
        assert boosted == pytest.approx(0.65 * (1 + 0.10 * 3))
        assert compute_importance(req, in_responsibilities=True) == pytest.approx(0.65 * 1.1)
        hard = make_requirement("Knowledge of AWS", mandatory=True)
        assert compute_importance(hard) == 1.0  # mandatory floor
        assert compute_importance(req, repetitions=99) <= 1.0

    def test_weights_are_configurable(self):
        req = make_requirement("Knowledge of AWS")
        strict = ImportanceWeights(knowledge=0.3)
        assert compute_importance(req, weights=strict) == pytest.approx(0.3)


# ---------------------------------------------------------------- evidence


SNAPSHOT = {
    "profile": {
        "full_name": "Shamique Khan",
        "headline": "AI Engineer",
        "summary": "AI engineer focused on RAG pipelines and multi-agent systems",
    },
    "experiences": [
        {
            "id": 1,
            "title": "AI Engineer Intern",
            "organization": "Suproc",
            "start_date": "Jul 2026",
            "end_date": "Present",
            "description": "",
            "bullets": [
                "Architected 4+ multi-model LLM agents in Python with LangGraph",
                "Improved ranking accuracy by 15% in production",
                "Mentored interns on agent tool calling",
            ],
            "tags": "langgraph,agents",
        },
    ],
    "projects": [
        {
            "id": 7,
            "name": "TensorFlow RAG Q&A Agent",
            "tech": "Python, LangChain, FAISS",
            "description": "",
            "bullets": [
                "Built end-to-end RAG pipeline over 500+ docs pages",
                "Segment-level road safety analytics platform",
            ],
            "link": "",
        },
    ],
    "education": [
        {"degree": "B.Tech CSE", "institution": "VIT",
         "start_date": "2025", "end_date": "2029", "details": "AI & ML"},
    ],
    "certifications": [
        {"name": "Oracle OCI Generative AI", "issuer": "Oracle", "year": "2026"},
    ],
    "skills": {"llm": ["Python", "LangChain", "LangGraph", "RAG"], "ml": ["XGBoost"]},
}


class TestEvidence:
    @pytest.fixture(scope="class")
    def pool(self) -> list[Evidence]:
        return evidence_from_snapshot(SNAPSHOT)

    def test_extracts_all_source_types(self, pool):
        ids = {e.id for e in pool}
        assert "exp-1-b0" in ids
        assert "prj-7-b0" in ids
        assert "skills-llm" in ids
        assert "edu-0" in ids
        assert "cert-0" in ids
        assert "profile-summary" in ids
        # empty descriptions produce no desc row
        assert "exp-1-desc" not in ids

    def test_bullet_provenance_fields(self, pool):
        bullet = next(e for e in pool if e.id == "exp-1-b0")
        assert bullet.source_type == "experience"
        assert bullet.source_id == "exp-1"
        assert bullet.company == "Suproc"
        assert bullet.role == "AI Engineer Intern"
        assert set(bullet.skills) >= {"Python", "LangGraph"}
        assert bullet.tools == ["langgraph", "agents"]
        assert "4+" in bullet.metrics

    def test_metrics_and_dates_extracted(self, pool):
        measured = next(e for e in pool if e.id == "exp-1-b1")
        assert "15%" in measured.metrics
        edu = next(e for e in pool if e.id == "edu-0")
        assert edu.dates == ["2025", "2029"]
        cert = next(e for e in pool if e.id == "cert-0")
        assert "2026" in cert.dates
        assert cert.strength >= 0.35

    def test_strength_follows_evidence_hierarchy(self, pool):
        by_id = {e.id: e for e in pool}
        skill_list = by_id["skills-llm"].strength
        project_plain = by_id["prj-7-b1"].strength
        experience_plain = by_id["exp-1-b2"].strength
        experience_measured = by_id["exp-1-b1"].strength
        assert skill_list == pytest.approx(0.25)
        assert project_plain == pytest.approx(0.55)
        assert experience_plain == pytest.approx(0.70)
        assert experience_measured == pytest.approx(0.90)  # 0.70 + measured
        assert skill_list < project_plain < experience_plain < experience_measured

    def test_deployment_marker_promotes_but_metric_wins(self):
        assert estimate_strength("experience", "Shipped the service") == pytest.approx(0.80)
        assert estimate_strength("experience", "Shipped with 99.9% uptime") == pytest.approx(0.90)

    def test_metric_extraction_excludes_years(self):
        assert extract_metrics("Led team in 2024 with 12% growth") == ["12%"]


# ---------------------------------------------------------------- ResumeIR


class TestResumeIR:
    def _resume(self) -> ResumeIR:
        return ResumeIR(
            header=HeaderIR(name="Shamique Khan", email="a@b.co"),
            experience=[
                {
                    "id": "exp-1",
                    "title": "AI Engineer Intern",
                    "organization": "Suproc",
                    "bullets": [
                        {
                            "text": "Architected 4+ multi-model LLM agents in Python",
                            "evidence_ids": ["exp-1-b0"],
                            "requirement_ids": ["req_python"],
                            "importance": 0.9,
                            "space_cost": 1,
                        }
                    ],
                }
            ],
        )

    def test_bullet_provenance_flows_through(self):
        resume = self._resume()
        assert resume.evidence_ids() == ["exp-1-b0"]
        bullet = resume.all_bullets()[0]
        assert bullet.requirement_ids == ["req_python"]
        assert bullet.importance == 0.9

    def test_space_accounting(self):
        resume = self._resume()
        assert resume.bullet_space() == 1
        assert resume.total_space() >= resume.bullet_space() + 3  # header block

    def test_estimate_lines(self):
        assert estimate_lines("") == 0
        assert estimate_lines("one two three") == 1
        assert estimate_lines(" ".join(["w"] * 24)) == 3  # ceil(24/11)

    def test_json_round_trip(self):
        resume = self._resume()
        again = ResumeIR.model_validate_json(resume.model_dump_json())
        assert again == resume
