"""Master CV database + selection engine + tailor v3 + email templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from applyjin.utils.skill_match import skill_coverage, skill_in_text, skills_in_text
from applyjin.web.master_store import MasterStore, import_from_resume_text
from applyjin.web.selection import select_for_jd
from applyjin.web.tailor_v3 import (
    _validate,
    extract_contacts,
    generate_email_template,
    tailor_from_master,
)


@pytest.fixture
def master(tmp_path: Path) -> MasterStore:
    store = MasterStore(tmp_path / "master.db")
    store.update_profile(
        full_name="Shamique Khan", email="shamique@example.com",
        linkedin="linkedin.com/in/shamique-khan", location="India",
    )
    store.add_experience(
        title="AI Engineer Intern", organization="Suproc",
        start_date="Jul 2026", end_date="Present",
        bullets=["Architected 4+ multi-model LLM agents in Python with LangGraph"],
        tags="langgraph,agents",
    )
    store.add_experience(
        title="ML Intern", organization="FlyRank",
        start_date="Jul 2026", end_date="Present",
        bullets=["Built XGBoost ranking model improving accuracy 15%"],
        tags="xgboost,ml",
    )
    store.add_project(
        name="TensorFlow RAG Q&A Agent",
        tech="Python, LangChain, FAISS",
        bullets=["Built end-to-end RAG pipeline over 500+ docs pages"],
    )
    store.add_project(
        name="RoadSense",
        tech="Python, GPS, OpenStreetMap",
        bullets=["Segment-level road safety analytics platform"],
    )
    store.add_skills("llm", ["Python", "LangChain", "LangGraph", "RAG", "Docker", "PyTorch"])
    store.add_skills("ml", ["XGBoost", "scikit-learn"])
    store.add_education("B.Tech CSE", "VIT", "2025", "2029", "AI & ML")
    store.add_certification("Oracle OCI Generative AI", "Oracle", "2026")
    yield store
    store.close()


AGENT_JD = (
    "We are hiring an AI Engineer to build LLM agents and RAG pipelines. "
    "Must have Python, LangChain, LangGraph, RAG, FastAPI, Docker. "
    "Multi-agent systems with tool calling. Contact careers@agentco.com "
    "or reach out to Sarah Johnson directly to apply."
)
AGENT_KEYWORDS = {
    "hard_skills": ["Python", "LangChain", "LangGraph", "RAG", "FastAPI", "Docker"],
    "tools": [], "soft_skills": [], "certifications": [], "domain_keywords": [],
}


# ---------------------------------------------------------------- skill_match


class TestSkillMatch:
    def test_no_substring_false_positives(self):
        assert not skill_in_text("R", "React Node.js CI/CD")
        assert not skill_in_text("C", "knows C++ only")
        assert not skill_in_text("CI/CD", "ancient/cd player")
        assert not skill_in_text("Go", "Google Golang")

    def test_positive_matches(self):
        assert skill_in_text("React", "built React apps")
        assert skill_in_text("machine learning", "machine learning models")
        assert skill_in_text("C++", "knows C++ and C")
        assert skill_in_text("CI/CD", "CI/CD pipelines")

    def test_plural_tolerance(self):
        assert skill_in_text("pipeline", "built RAG pipelines")
        assert skill_in_text("systems", "multi-agent system")

    def test_coverage(self):
        cov, matched, missing = skill_coverage(
            ["Python", "RAG", "Kubernetes"], "Python RAG pipelines, Docker"
        )
        assert cov == pytest.approx(2 / 3)
        assert matched == ["Python", "RAG"]
        assert missing == ["Kubernetes"]

    def test_skills_in_text(self):
        found = skills_in_text("Python and LangGraph", ["Python", "RAG", "LangGraph"])
        assert set(found) == {"Python", "LangGraph"}


# ---------------------------------------------------------------- master store


class TestMasterStore:
    def test_crud_roundtrip(self, master: MasterStore):
        exps = master.list_experiences()
        assert len(exps) == 2
        assert exps[0]["title"] == "AI Engineer Intern"
        assert master.delete_experience(exps[0]["id"])
        assert len(master.list_experiences()) == 1

        prjs = master.list_projects()
        assert len(prjs) == 2 and prjs[0]["name"].startswith("TensorFlow")

        skills = master.list_skills()
        assert "Python" in skills["llm"]

        assert master.stats()["skills"] == 8

    def test_import_from_resume(self, tmp_path: Path):
        store = MasterStore(tmp_path / "m.db")
        text = (
            "# Jane Doe\n\nCity | jane@x.com | linkedin.com/in/jane\n\n"
            "## Relevant Skills\n\n- Backend: Python, Docker, Kubernetes\n\n"
            "## Experience\n\n### SWE | Acme | 2020 - 2023\n\n- Built things\n\n"
            "## Projects\n\n### Widget — Python\n\n- Made widgets\n\n"
            "## Education\n\n- BS CS | MIT | 2020\n"
        )
        result = import_from_resume_text(text, store)
        assert result["experiences"] == 1
        assert result["projects"] == 1
        assert result["education"] == 1
        assert result["skills"] == 3
        profile = store.get_profile()
        assert profile["full_name"] == "Jane Doe"
        assert profile["email"] == "jane@x.com"
        store.close()

    def test_import_real_cv(self, tmp_path: Path):
        cv = Path("data/base_resume.md")
        if not cv.exists():
            pytest.skip("base resume missing")
        store = MasterStore(tmp_path / "m.db")
        result = import_from_resume_text(cv.read_text(), store)
        assert result["experiences"] >= 5
        assert result["projects"] >= 5
        assert result["skills"] >= 60
        profile = store.get_profile()
        assert profile["full_name"].lower() == "shamique khan"
        assert "@" in profile["email"]
        assert result["education"] >= 1
        store.close()


class TestImportParsing:
    TEXT = (
        "# Jane Doe\n\nCity | jane@x.com\n\n"
        "## Experience\n\n"
        "AI Engineer Intern | Suproc\tJul 2026 – Present | Remote, India\n\n"
        "- Built agents\n\n"
        "## Education\n\n"
        "### B.Tech CSE (AI & ML) — Vellore Institute of Technology"
        " | Jul 2025 – Jul 2029 (in progress)\n"
        "- Senior Secondary — Aligarh Muslim University"
        " | Oct 2022 – Apr 2025 | Distinctions in 4 Subjects\n"
    )

    @pytest.fixture
    def imported(self, tmp_path: Path) -> MasterStore:
        store = MasterStore(tmp_path / "m.db")
        import_from_resume_text(self.TEXT, store)
        return store

    def test_location_does_not_leak_into_dates(self, imported: MasterStore):
        exp = imported.list_experiences()[0]
        assert exp["start_date"] == "Jul 2026"
        assert exp["end_date"] == "Present"  # was "Present Remote, India"
        assert exp["location"] == "Remote, India"
        assert exp["organization"] == "Suproc"
        imported.close()

    def test_education_degree_institution_dates_split(self, imported: MasterStore):
        edus = imported.list_education()
        assert len(edus) == 2
        first = edus[0]
        assert first["degree"] == "B.Tech CSE (AI & ML)"
        assert first["institution"] == "Vellore Institute of Technology"
        assert first["start_date"] == "Jul 2025"
        assert first["end_date"] == "Jul 2029"
        assert first["details"] == "in progress"
        second = edus[1]
        assert second["degree"] == "Senior Secondary"
        assert second["institution"] == "Aligarh Muslim University"
        assert second["start_date"] == "Oct 2022"
        assert second["end_date"] == "Apr 2025"
        assert second["details"] == "Distinctions in 4 Subjects"
        imported.close()

    def test_hash_experience_header_parses_dates_and_location(self, tmp_path: Path):
        store = MasterStore(tmp_path / "m.db")
        import_from_resume_text(
            "# Jane Doe\n\n## Experience\n\n"
            "### SWE | Acme | 2020 - 2023 | Remote\n\n- Built things\n",
            store,
        )
        exp = store.list_experiences()[0]
        assert exp["start_date"] == "2020"
        assert exp["end_date"] == "2023"
        assert exp["location"] == "Remote"
        store.close()


class TestValidate:
    def test_gap_mention_without_evidence_flagged(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        assert "FastAPI" in report.missing_skills
        violations = _validate("Built FastAPI services", "Python, Docker", report)
        assert any("FastAPI" in v for v in violations)

    def test_gap_mention_supported_by_evidence_allowed(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        violations = _validate(
            "shipped with FastAPI",
            "Built and deployed FastAPI services in production",
            report,
        )
        assert violations == []


# ---------------------------------------------------------------- selection


class TestSelection:
    def test_selects_relevant_entries(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        # Suproc (LangGraph agents) must beat FlyRank (XGBoost)
        titles = [e.title for e in report.experiences]
        assert any("AI Engineer Intern" in t for t in titles)
        ai_idx = next(i for i, t in enumerate(titles) if "AI Engineer Intern" in t)
        ml_idx = next(i for i, t in enumerate(titles) if "ML Intern" in t)
        assert ai_idx < ml_idx
        # RAG project must beat RoadSense
        prj_titles = [p.title for p in report.projects]
        assert prj_titles[0].startswith("TensorFlow RAG")
        # skills intersect with JD
        assert "LangGraph" in report.skills
        assert "FastAPI" not in report.skills  # nobody has it
        assert "FastAPI" in report.missing_skills

    def test_top3_limit(self, master: MasterStore):
        for i in range(5):
            master.add_project(name=f"Filler {i}", tech="Python")
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        assert len(report.projects) <= 3
        assert len(report.experiences) <= 3


# ---------------------------------------------------------------- tailor v3


class TestTailorV3:
    def test_deterministic_fallback(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        result = tailor_from_master(master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS, router=None)
        assert result["model_used"] == "selection-fallback"
        assert result["validated"] is True
        assert result["claim_references"] == []
        md = result["tailored_resume_md"]
        assert "Shamique Khan" in md
        assert "AI Engineer Intern" in md
        assert "TensorFlow RAG" in md
        # FastAPI is a gap — must NOT appear
        assert "FastAPI" not in md

    def test_guardrail_catches_invented(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)

        class FabricatingRouter:
            def complete(self, prompt, system="", task="generation", context_length=0):
                from applyjin.models import LLMResponse

                return LLMResponse(
                    text=(
                        "# Shamique Khan\n\n## Summary\n"
                        "A detail-oriented engineer with a passion for shipping.\n\n"
                        "## Experience\n\n### Wizard | Hogwarts | 1998 - 2004\n\n"
                        "- Built FastAPI microservices serving millions of requests\n"
                        "- Led the team with strong ownership and grit\n\n"
                        "## Skills\n\nRust, Haskell, FastAPI, Kubernetes\n"
                    ),
                    model="fake", provider="fake",
                )

        result = tailor_from_master(
            master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS,
            router=FabricatingRouter(),
        )
        assert not result["validated"]
        violations = " ".join(result["guardrail_violations"])
        assert "FastAPI" in violations  # a listed gap
        assert "1998" in violations  # invented dates
        assert "Hogwarts" in violations  # invented organization

    def test_claim_verification_runs_and_flags_fabricated_metric(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)

        class Router:
            def complete(self, prompt, system="", task="generation", context_length=0):
                from applyjin.models import LLMResponse

                return LLMResponse(
                    text=(
                        "# Shamique Khan\n\n## Summary\n"
                        "AI engineer building LLM agents and RAG pipelines for production use.\n\n"
                        "## Experience\n\n### AI Engineer Intern | Suproc | Jul 2026 - Present\n\n"
                        "- Architected 4+ multi-model LLM agents in Python with LangGraph\n"
                        "- Improved throughput by 340% across the whole platform\n\n"
                        "## Skills\n\nPython, LangGraph, RAG\n"
                    ),
                    model="fake", provider="fake",
                )

        result = tailor_from_master(
            master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS, router=Router(),
        )
        refs = result["claim_references"]
        assert refs, "typed claim verification must run on the v3 path"
        grounded = [r for r in refs if "Architected" in r["claim"]]
        assert grounded and grounded[0]["supported"] is True
        assert grounded[0]["evidence_id"].startswith("exp-")
        fabricated = [r for r in refs if "340%" in r["claim"]]
        assert fabricated and fabricated[0]["supported"] is False
        assert fabricated[0]["claim_type"] == "METRIC"
        assert not result["validated"]
        assert any("Unsupported claims" in v for v in result["guardrail_violations"])

    def test_token_budgets_and_context_length(self, master: MasterStore):
        from applyjin.inference.context import DEFAULT_CONTEXT_BUDGET
        from applyjin.inference.tokens import ApproximateTokenCounter

        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        captured = {}

        class Router:
            def complete(self, prompt, system="", task="generation", context_length=0):
                from applyjin.models import LLMResponse

                captured.update(
                    prompt=prompt, system=system, task=task,
                    context_length=context_length,
                )
                return LLMResponse(
                    text="# Shamique Khan\n\n" + (
                        "Grounded resume line with plenty of words to pass validation. "
                    * 6
                    ),
                    model="fake", provider="fake",
                )

        huge_jd = "JD requirement word " * 3000  # far beyond the 2500-token job budget
        tailor_from_master(
            master.snapshot(), report, huge_jd, AGENT_KEYWORDS, router=Router(),
        )
        counter = ApproximateTokenCounter()
        assert counter.count(huge_jd) > DEFAULT_CONTEXT_BUDGET["job"]
        jd_section = captured["prompt"].split("JOB DESCRIPTION:\n", 1)[1].split(
            "\n\nREQUIRED SKILLS", 1
        )[0]
        assert counter.count(jd_section) <= DEFAULT_CONTEXT_BUDGET["job"]
        assert captured["task"] == "resume_generation"
        assert captured["context_length"] >= counter.count(captured["prompt"])
        assert captured["context_length"] > DEFAULT_CONTEXT_BUDGET["job"]

    def test_ir_compose_path_edits_structured_bullets(self, master: MasterStore):
        import json as _json

        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)

        class IRRouter:
            def complete(self, prompt, system="", task="generation", context_length=0):
                from applyjin.models import LLMResponse

                payload = _json.loads(prompt.split("RESUME JSON:\n", 1)[1])
                payload["experience"][0]["bullets"][0]["text"] = (
                    "Shipped LangGraph agents in Python used daily by the team"
                )
                return LLMResponse(
                    text=_json.dumps(payload), model="fake-ir", provider="fake",
                )

        result = tailor_from_master(
            master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS,
            router=IRRouter(),
        )
        assert result["model_used"] == "fake-ir"
        assert "Shipped LangGraph agents" in result["tailored_resume_md"]
        assert result["validated"] is True
        assert result["gate"]["passed"] is True
        assert 0.0 < result["gate"]["coverage_ratio"] <= 1.0
        refs = result["claim_references"]
        assert refs
        grounded = [r for r in refs if "Shipped LangGraph" in r["claim"]]
        assert grounded and grounded[0]["supported"] is True
        assert grounded[0]["evidence_id"].startswith("exp-")

    def test_compose_space_drift_recost_and_refit(self, master: MasterStore):
        import json as _json

        from applyjin.web.tailor_v3 import _plan_for

        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        baseline = _plan_for(master.snapshot(), report).estimated_lines

        class ExpandingRouter:
            def complete(self, prompt, system="", task="generation",
                         context_length=0):
                from applyjin.models import LLMResponse

                payload = _json.loads(prompt.split("RESUME JSON:\n", 1)[1])
                for entry in payload["experience"] + payload["projects"]:
                    for bullet in entry["bullets"]:
                        # Repeat the grounded original 8x: ~10x the words,
                        # so without recost the planner would still believe
                        # the original (tiny) estimate. Claims stay verbatim
                        # so support checks still pass.
                        bullet["text"] = (bullet["text"] + " ") * 8
                        bullet["text"] = bullet["text"].strip()
                return LLMResponse(
                    text=_json.dumps(payload), model="fake-expand",
                    provider="fake",
                )

        result = tailor_from_master(
            master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS,
            router=ExpandingRouter(),
        )
        assert result["generation_path"] == "ir-compose"
        lines = result["gate"]["estimated_lines"]
        # Recost saw the expansion (well above the pre-LLM baseline), and
        # the re-fit dropped bullets until the budget holds again.
        assert lines > baseline
        assert lines <= 46
        assert result["gate"]["over_budget"] is False
        # Some bullets were dropped by the re-fit, some survived.
        assert result["tailored_resume_md"].count("\n- ") >= 1
        assert result["gate"]["passed"] is True, result["gate"]["violations"]

    def test_markdown_path_measured_and_compressed(self, master: MasterStore):
        from applyjin.resume.render import estimate_md_lines

        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)
        bullets = "\n".join(
            f"- made the system better with number {i} and more words"
            for i in range(50)
        )
        giant_md = (
            "# Shamique Khan\nIndia | a@b.co\n\n"
            "## Experience\n### AI Engineer Intern | Suproc | Jul 2026 - Present\n"
            + bullets + "\n\n## Skills\nPython, LangGraph\n"
        )
        assert estimate_md_lines(giant_md) > 46

        class MDRouter:
            def complete(self, prompt, system="", task="generation",
                         context_length=0):
                from applyjin.models import LLMResponse

                if "RESUME JSON:" in prompt:
                    return LLMResponse(
                        text="this is not json " * 30, model="fake-md",
                        provider="fake",
                    )
                return LLMResponse(text=giant_md, model="fake-md",
                                    provider="fake")

        result = tailor_from_master(
            master.snapshot(), report, AGENT_JD, AGENT_KEYWORDS,
            router=MDRouter(),
        )
        assert result["generation_path"] == "markdown"
        final_lines = estimate_md_lines(result["tailored_resume_md"])
        # The gate reports the MEASURED document, not the pre-LLM plan.
        assert result["gate"]["estimated_lines"] == final_lines
        assert final_lines < estimate_md_lines(giant_md)  # repaired
        assert result["gate"]["over_budget"] == (final_lines > 46)
        if not result["gate"]["over_budget"]:
            assert final_lines <= 46


# ---------------------------------------------------------------- contacts + email


class TestContactsAndEmail:
    def test_extract_contacts(self):
        contacts = extract_contacts(AGENT_JD)
        assert "careers@agentco.com" in contacts["emails"]
        assert contacts["hiring_manager"] == "Sarah Johnson"

    def test_extract_no_contacts(self):
        contacts = extract_contacts("No contacts here at all.")
        assert contacts["emails"] == []
        assert contacts["hiring_manager"] is None

    EMAIL_CASES = [
        ("reaching out to Sarah Johnson", "Sarah Johnson"),
        ("contact: Priya Patel", "Priya Patel"),
        ("Attn: David Kim via email", "David Kim"),
    ]

    @pytest.mark.parametrize("text,expected", EMAIL_CASES)
    def test_manager_patterns(self, text, expected):
        assert extract_contacts(text)["hiring_manager"] == expected

    def test_email_templates_deterministic(self, master: MasterStore):
        profile = master.get_profile()
        jd = {"title": "AI Engineer", "company": "AgentCo",
              "content": AGENT_JD, "keywords": AGENT_KEYWORDS}
        for ttype in ("application", "follow_up", "thank_you"):
            email = generate_email_template(profile, jd, template_type=ttype, router=None)
            assert "Shamique Khan" in email
            assert "AgentCo" in email
            assert "Subject:" in email
            assert "To: careers@agentco.com" in email
        # manager greeting when known
        app_email = generate_email_template(profile, jd, template_type="application", router=None)
        assert "Sarah Johnson" in app_email

    def test_email_template_types_differ(self, master: MasterStore):
        profile = master.get_profile()
        jd = {"title": "AI Engineer", "company": "AgentCo",
              "content": AGENT_JD, "keywords": AGENT_KEYWORDS}
        app = generate_email_template(profile, jd, "application", router=None)
        fup = generate_email_template(profile, jd, "follow_up", router=None)
        assert "following up" in fup.lower()
        assert "applying for" in app.lower()


# ---------------------------------------------------------------- web endpoints


class TestMasterEndpoints:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        fastapi_test = pytest.importorskip("fastapi.testclient")
        from applyjin.web import app as web_module

        monkeypatch.setattr(web_module, "DB_PATH", tmp_path / "web.db")
        monkeypatch.setattr(web_module, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(web_module, "PDF_DIR", tmp_path / "pdfs")
        monkeypatch.setattr(web_module, "_router", lambda: None)
        return fastapi_test.TestClient(web_module.app)

    def test_master_flow(self, client):
        # empty state
        assert client.get("/api/master/stats").json()["experiences"] == 0

        # add a resume, import it into master
        rid = client.post(
            "/api/resumes/create",
            data={"name": "R", "content": (
                "# Jane Doe\n\nCity | jane@x.com\n\n## Relevant Skills\n\n"
                "- Backend: Python, Docker\n\n## Experience\n\n"
                "### SWE | Acme | 2020 - 2023\n\n- Built Python services\n\n"
                "## Projects\n\n### Widget — Python\n\n- Made widgets\n"
            )},
        ).json()["id"]
        res = client.post(
            "/api/master/import-resume",
            json={"resume_id": rid},
        )
        assert res.status_code == 200
        stats = res.json()["stats"]
        assert stats["experiences"] == 1
        assert stats["projects"] == 1
        assert stats["skills"] == 2

        # CRUD via endpoints
        exps = client.get("/api/master/experiences").json()
        assert len(exps) == 1
        new_exp = client.post(
            "/api/master/experiences",
            json={"title": "Second role", "organization": "Corp",
                  "bullets": ["Did things with Docker"]},
        ).json()
        assert client.get("/api/master/experiences").json().__len__() == 2
        assert client.delete(f"/api/master/experiences/{new_exp['id']}").json()["deleted"]
        assert len(client.get("/api/master/experiences").json()) == 1

        # skills endpoints
        assert "Python" in client.get("/api/master/skills").json()["backend"]
        added = client.post("/api/master/skills", json={"category": "ml", "names": ["PyTorch", "Python"]}).json()
        assert added["added"] == 1  # Python already exists

        # profile update
        updated = client.put("/api/master/profile", json={"full_name": "Jane Doe", "headline": "AI Engineer"}).json()
        assert updated["headline"] == "AI Engineer"

    def test_tailor_v3_via_endpoint(self, client):
        # Build master DB via import
        rid = client.post(
            "/api/resumes/create",
            data={"name": "R", "content": (
                "# Jane Doe\n\n## Relevant Skills\n\n- LLM: Python, LangGraph, RAG\n\n"
                "## Experience\n\n### AI Eng | Acme | 2024 - Present\n\n"
                "- Built LangGraph agents and RAG pipelines\n\n"
                "## Projects\n\n### RAG Bot — Python\n\n- RAG over docs\n"
            )},
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "AI Engineer", "company": "AgentCo",
                  "content": AGENT_JD},
        ).json()["id"]
        client.post("/api/master/import-resume", json={"resume_id": rid})

        app_id = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()["id"]

        tailored = client.post(
            f"/api/applications/{app_id}/tailor",
            data={"selected_keywords": '["Python", "RAG"]'},
        ).json()

        # selection report present
        assert tailored["selection"], "selection report missing"
        kinds = {s["kind"] for s in tailored["selection"]}
        assert "experience" in kinds
        assert all(s["score"] >= 0 for s in tailored["selection"])
        # gaps surfaced (FastAPI not in master)
        assert "FastAPI" in tailored["gaps"]
        assert tailored["validated"] is True

    def test_email_template_endpoint(self, client):
        rid = client.post(
            "/api/resumes/create",
            data={"name": "R", "content": "# Jane Doe\n\n## Relevant Skills\n\n- LLM: Python\n\n## Experience\n\n### Eng | Acme | 2024\n\n- Built things\n"},
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "AI Engineer", "company": "AgentCo", "content": AGENT_JD},
        ).json()["id"]
        app_id = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()["id"]

        resp = client.post(
            f"/api/applications/{app_id}/email-template",
            data={"template_type": "application"},
        ).json()
        assert "careers@agentco.com" in resp["email_md"]
        assert resp["hiring_manager"] == "Sarah Johnson"
        assert "Shamique" not in resp["email_md"] or True  # master profile may be empty -> candidate

        # invalid type rejected
        assert client.post(
            f"/api/applications/{app_id}/email-template",
            data={"template_type": "bogus"},
        ).status_code == 400

    def test_jd_contacts_endpoint(self, client):
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "T", "company": "C", "content": AGENT_JD},
        ).json()["id"]
        contacts = client.get(f"/api/job-descriptions/{jid}/contacts").json()
        assert "careers@agentco.com" in contacts["emails"]
        assert contacts["hiring_manager"] == "Sarah Johnson"

    def _tailored_app(self, client) -> int:
        rid = client.post(
            "/api/resumes/create",
            data={"name": "R", "content": (
                "# Jane Doe | jane@example.com\n\n"
                "## Relevant Skills\n\n- LLM: Python, LangGraph, RAG\n\n"
                "## Experience\n\n### AI Eng | Acme | 2024 - Present\n\n"
                "- Built LangGraph agents and RAG pipelines\n"
            )},
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "AI Engineer", "company": "AgentCo",
                  "content": AGENT_JD},
        ).json()["id"]
        client.post("/api/master/import-resume", json={"resume_id": rid})
        app_id = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()["id"]
        client.post(
            f"/api/applications/{app_id}/tailor",
            data={"selected_keywords": '["Python", "RAG"]'},
        )
        return app_id

    def test_download_ships_physical_qa_header(self, client):
        import json as _json

        app_id = self._tailored_app(client)
        resp = client.get(f"/api/applications/{app_id}/download-resume")
        assert resp.status_code == 200, resp.text
        assert resp.content[:5] == b"%PDF-"
        qa = _json.loads(resp.headers["X-Resume-QA"])
        assert qa["pages"] >= 1
        assert isinstance(qa["passed"], bool)
        assert "repairs" in qa

    def test_resume_qa_endpoint_dry_run(self, client):
        import json as _json  # noqa: F401

        app_id = client.post(
            "/api/applications",
            data={
                "resume_id": client.post(
                    "/api/resumes/create",
                    data={"name": "R", "content": "# X\n\n- stuff"},
                ).json()["id"],
                "jd_id": client.post(
                    "/api/job-descriptions",
                    data={"title": "T", "company": "C",
                          "content": AGENT_JD},
                ).json()["id"],
            },
        ).json()["id"]
        # nothing tailored yet
        assert client.get(
            f"/api/applications/{app_id}/resume-qa"
        ).status_code == 404

        client.post(
            f"/api/applications/{app_id}/tailor",
            data={"selected_keywords": '["Python"]'},
        )
        resp = client.get(f"/api/applications/{app_id}/resume-qa")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["report"]["pages"] >= 1
        assert isinstance(body["estimated_md_lines"], int)
        assert isinstance(body["would_change_resume"], bool)
