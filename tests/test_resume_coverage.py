"""Phase 2: requirement extraction, marginal-coverage selection, wiring."""

from __future__ import annotations

from applyjin.resume.coverage import (
    CoverageItem,
    requirement_covers,
    select_by_marginal_coverage,
)
from applyjin.resume.extract import (
    extract_requirements,
    requirements_from_keywords,
)
from applyjin.resume.requirements import make_requirement
from applyjin.utils.llm_router import LLMUnavailable
from applyjin.web.selection import select_for_jd

KEYWORDS = {
    "hard_skills": ["Python", "LangGraph", "XGBoost"],
    "tools": ["FastAPI"],
    "soft_skills": ["communication"],
    "certifications": [],
    "domain_keywords": ["recommendation systems"],
}

JD = (
    "Hiring an AI Engineer. Experience with Python and LangGraph agents. "
    "Recommendation systems team. marketing marketing marketing marketing."
)


# ---------------------------------------------------------------- extractor


class TestRequirementsFromKeywords:
    def test_buckets_map_to_categories_and_tiers(self):
        reqs = {r.text: r for r in requirements_from_keywords(KEYWORDS, JD)}
        assert reqs["Experience with Python"].category == "TECHNICAL_SKILL"
        assert reqs["Experience with Python"].importance == 0.95
        assert reqs["Experience with FastAPI"].category == "TOOL"
        assert reqs["communication"].category == "SOFT_SKILL"
        assert reqs["communication"].importance == 0.25
        assert reqs["Knowledge of recommendation systems"].category == "DOMAIN"
        assert reqs["Knowledge of recommendation systems"].importance == 0.55

    def test_repetition_raises_importance(self):
        jd = " ".join(["Recommendation systems"] * 4)
        reqs = {r.text: r for r in requirements_from_keywords(KEYWORDS, jd)}
        domain = reqs["Knowledge of recommendation systems"]
        # "recommendation systems" appears 4x -> 0.55 x 1.3 = 0.715
        assert domain.importance == 0.715

    def test_deterministic_ids_and_dedupe(self):
        first = requirements_from_keywords(KEYWORDS, JD)
        second = requirements_from_keywords(KEYWORDS, JD)
        assert [r.id for r in first] == [r.id for r in second]
        dup = dict(KEYWORDS)
        dup["tools"] = ["Python"]
        texts = [r.text for r in requirements_from_keywords(dup, JD)]
        assert texts.count("Experience with Python") == 1

    def test_sorted_by_importance_desc(self):
        reqs = requirements_from_keywords(KEYWORDS, JD)
        weights = [r.importance for r in reqs]
        assert weights == sorted(weights, reverse=True)


class _FakeRouter:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, prompt: str, system: str = ""):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class TestExtractRequirements:
    PAYLOAD = {
        "requirements": [
            {"text": "Must have Kubernetes experience", "category": "TOOL",
             "explicitness": "must_have", "mandatory": True},
            {"text": "Experience building RAG agents",
             "category": "FRAMEWORK", "explicitness": "experience",
             "aliases": ["Retrieval-Augmented Generation"]},
            {"text": "Familiarity with FastAPI", "explicitness": "familiarity"},
            {"text": "Know AWS", "category": "NOT_A_CATEGORY",
             "explicitness": "unknown-tier"},
            {"text": "Excellent communication", "category": "SOFT_SKILL",
             "explicitness": "knowledge"},
        ]
    }

    def test_llm_path_parses_tiers_categories_aliases(self):
        reqs, source = extract_requirements(JD, KEYWORDS, _FakeRouter(self.PAYLOAD))
        assert source == "llm"
        by_text = {r.text: r for r in reqs}
        k8s = by_text["Must have Kubernetes experience"]
        assert k8s.category == "TOOL"
        assert k8s.importance == 1.0
        assert k8s.mandatory and k8s.evidence_required
        rag = by_text["Experience building RAG agents"]
        assert rag.category == "FRAMEWORK"
        assert rag.importance == 0.95
        assert rag.aliases == ["rag"]
        assert by_text["Familiarity with FastAPI"].importance == 0.65
        # invalid category/explicitness get defaults
        assert by_text["Know AWS"].category == "TECHNICAL_SKILL"
        assert by_text["Know AWS"].importance == 0.70
        # soft skills stay capped even with a high explicitness tier
        assert by_text["Excellent communication"].importance == 0.25
        assert [r.importance for r in reqs] == sorted(
            (r.importance for r in reqs), reverse=True
        )

    def test_bare_list_payload_accepted(self):
        reqs, source = extract_requirements(
            JD, KEYWORDS, _FakeRouter([{"text": "Experience with Docker"}])
        )
        assert source == "llm"
        assert reqs[0].text == "Experience with Docker"

    def test_falls_back_when_router_down(self):
        reqs, source = extract_requirements(
            JD, KEYWORDS, _FakeRouter(LLMUnavailable("down"))
        )
        assert source == "keywords"
        assert reqs == requirements_from_keywords(KEYWORDS, JD)

    def test_falls_back_on_malformed_payload(self):
        _, source = extract_requirements(
            JD, KEYWORDS, _FakeRouter({"requirements": "not-a-list"})
        )
        assert source == "keywords"

    def test_no_router_is_instant(self):
        reqs, source = extract_requirements(JD, KEYWORDS, None)
        assert source == "keywords"
        assert reqs


# ---------------------------------------------------------------- coverage


class TestRequirementCovers:
    def test_exact_phrase_with_plurals(self):
        req = make_requirement("Experience with vector databases")
        assert requirement_covers(req, "Used vector databases for retrieval")
        assert requirement_covers(req, "One vector database shipped")
        assert not requirement_covers(req, "CRM dashboards")

    def test_alias_concept(self):
        req = make_requirement("Experience with retrieval-augmented generation")
        assert req.normalized == "rag"
        assert requirement_covers(req, "Built a RAG pipeline over 500 pages")
        assert not requirement_covers(req, "Cold email campaigns")

    def test_fuzzy_majority_for_responsibilities(self):
        req = make_requirement(
            "Own the retrieval pipeline end to end", category="RESPONSIBILITY"
        )
        assert requirement_covers(req, "Built a retrieval pipeline for search")
        assert not requirement_covers(req, "Sales enablement decks")


class TestMarginalCoverage:
    def _items(self) -> list[CoverageItem]:
        return [
            CoverageItem("exp-1", "experience", "Python LangChain agents", 0.90),
            CoverageItem("exp-2", "experience", "Python FastAPI services", 0.85),
            CoverageItem("exp-3", "experience", "Unrelated sales tools", 0.95),
            CoverageItem("prj-1", "project", "XGBoost ranking model", 0.70),
        ]

    def _reqs(self):
        return [
            make_requirement("Experience with Python"),
            make_requirement("Experience with FastAPI"),
            make_requirement("Experience with XGBoost"),
        ]

    def test_coverage_beats_redundant_high_scores(self):
        picked = select_by_marginal_coverage(
            self._items(), self._reqs(),
            budgets={"experience": 2, "project": 1},
        )
        keys = [i.key for i in picked]
        # exp-2 covers two requirements at once; the redundant exp-1 loses
        # to coverage even though exp-3 has the best raw score.
        assert set(keys) == {"exp-2", "exp-3", "prj-1"}
        assert "exp-1" not in keys

    def test_deterministic_under_input_order(self):
        budgets = {"experience": 2, "project": 1}
        a = select_by_marginal_coverage(self._items(), self._reqs(), budgets)
        b = select_by_marginal_coverage(
            list(reversed(self._items())), self._reqs(), budgets
        )
        assert [i.key for i in a] == [i.key for i in b]

    def test_fills_budgets_when_candidates_run_short(self):
        picked = select_by_marginal_coverage(
            self._items()[:2], self._reqs(),
            budgets={"experience": 3, "project": 1},
        )
        assert len(picked) == 2

    def test_empty_requirements_degrades_to_relevance(self):
        picked = select_by_marginal_coverage(
            self._items(), [], budgets={"experience": 2, "project": 1}
        )
        keys = [i.key for i in picked]
        assert set(keys) == {"exp-3", "exp-1", "prj-1"}


# ---------------------------------------------------------------- selection


SNAPSHOT = {
    "profile": {"full_name": "Shamique Khan", "email": "a@b.co"},
    "experiences": [
        {"id": 1, "title": "AI Engineer Intern", "organization": "Suproc",
         "start_date": "Jul 2026", "end_date": "Present",
         "bullets": ["Architected 4+ multi-model LLM agents in Python with LangGraph"],
         "tags": "langgraph,agents"},
        {"id": 2, "title": "ML Intern", "organization": "FlyRank",
         "start_date": "Jul 2026", "end_date": "Present",
         "bullets": ["Built XGBoost ranking model improving accuracy 15%"],
         "tags": "xgboost,ml"},
        {"id": 3, "title": "Sales Analyst", "organization": "Acme",
         "start_date": "Jan 2025", "end_date": "Jun 2026",
         "bullets": ["Built CRM dashboards for outreach reporting"],
         "tags": "crm"},
    ],
    "projects": [
        {"id": 1, "name": "TensorFlow RAG Q&A Agent",
         "tech": "Python, LangChain, FAISS",
         "bullets": ["Built end-to-end RAG pipeline over 500+ docs pages"]},
    ],
    "skills": {"core": ["Python", "LangGraph", "XGBoost", "FastAPI"]},
}

SNAPSHOT_JD = (
    "AI Engineer building LLM agents. Experience with Python and "
    "LangGraph required. Needs XGBoost for ranking. Must have Kubernetes."
)


class TestSelectForJdWithRequirements:
    def _requirements(self):
        return requirements_from_keywords(KEYWORDS, SNAPSHOT_JD) + [
            make_requirement("Experience with Kubernetes")
        ]

    def test_wires_requirements_coverage_and_gaps(self):
        report = select_for_jd(
            SNAPSHOT, KEYWORDS, SNAPSHOT_JD,
            top_experiences=2, top_projects=1,
            requirements=self._requirements(),
        )
        assert report.requirements
        # every mapped requirement maps to a *selected* entry
        selected_keys = {f"exp-{e.id}" for e in report.experiences} | {
            f"prj-{p.id}" for p in report.projects
        }
        assert report.coverage_map
        assert set(report.coverage_map.values()) <= selected_keys
        # requirements nothing in the master DB supports are gaps
        assert any("Kubernetes" in text for text in report.uncovered_requirements)
        assert len(report.experiences) <= 2
        assert "requirements:" in "\n".join(report.summary_lines())

    def test_without_requirements_behaves_as_before(self):
        report = select_for_jd(SNAPSHOT, KEYWORDS, SNAPSHOT_JD)
        assert report.requirements == []
        assert report.coverage_map == {}
        assert report.uncovered_requirements == []

    def test_skillish_concepts_extend_skills_and_gaps(self):
        kubernetes = make_requirement(
            "Experience with Kubernetes", category="TECHNICAL_SKILL"
        )
        report = select_for_jd(
            SNAPSHOT, KEYWORDS, SNAPSHOT_JD, requirements=[kubernetes]
        )
        assert "kubernetes" in report.missing_skills

    def test_selection_covers_uniquely_matching_entry(self):
        # The XGBoost entry only ranks behind the agent entry, but the JD
        # demands XGBoost — coverage must pull it into a 2-slot budget.
        requirements = [
            make_requirement("Experience with Python"),
            make_requirement("Experience with XGBoost"),
        ]
        report = select_for_jd(
            SNAPSHOT, KEYWORDS, SNAPSHOT_JD,
            top_experiences=2, top_projects=0, requirements=requirements,
        )
        exp_ids = [e.id for e in report.experiences]
        assert 2 in exp_ids  # the XGBoost entry earned its slot
        assert report.coverage_map
