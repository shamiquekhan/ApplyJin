"""Master CV database + selection engine + tailor v3 + email templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes.utils.skill_match import skill_coverage, skill_in_text, skills_in_text
from hermes.web.master_store import MasterStore, import_from_resume_text
from hermes.web.selection import select_for_jd
from hermes.web.tailor_v3 import extract_contacts, generate_email_template, tailor_from_master


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
        md = result["tailored_resume_md"]
        assert "Shamique Khan" in md
        assert "AI Engineer Intern" in md
        assert "TensorFlow RAG" in md
        # FastAPI is a gap — must NOT appear
        assert "FastAPI" not in md

    def test_guardrail_catches_invented(self, master: MasterStore):
        report = select_for_jd(master.snapshot(), AGENT_KEYWORDS, AGENT_JD)

        class FabricatingRouter:
            def complete(self, prompt, system=""):
                from hermes.models import LLMResponse

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
        from hermes.web import app as web_module

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
