"""Phase 3: IR lifting from selection and the page-budget planner."""

from __future__ import annotations

from applyjin.resume.ir import (
    CertificationIR,
    EducationIR,
    ExperienceIR,
    HeaderIR,
    ResumeBullet,
    ResumeIR,
)
from applyjin.resume.planner import (
    PAGE_LINE_BUDGET,
    SECTION_ORDER,
    ResumePlan,
    ir_from_selection,
    plan_resume,
)
from applyjin.resume.requirements import make_requirement

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
         "bullets": ["Wrote internal docs", "Built XGBoost ranking model 15%"]},
        {"id": 2, "title": "Sales Analyst", "organization": "Acme",
         "start_date": "Jan 2025", "end_date": "Jun 2026",
         "bullets": ["CRM dashboards"]},
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
    "skills": {"ml": ["XGBoost", "Kubernetes"], "core": ["Python", "FastAPI"]},
}

REQUIREMENTS = [
    make_requirement("Experience with Python"),
    make_requirement("Experience with XGBoost"),
    make_requirement("Experience with Kubernetes"),  # no master evidence
]


def _selection_ir():
    return ir_from_selection(
        SNAPSHOT,
        selected_experience_ids=[1],
        selected_project_ids=[4],
        requirements=REQUIREMENTS,
        skills=["Python", "XGBoost"],
    )


class TestIRFromSelection:
    def test_header_summary_and_fixed_sections(self):
        ir = _selection_ir()
        assert ir.header.name == "Shamique Khan"
        assert ir.header.email == "a@b.co"
        assert ir.summary and "AI Engineer" in ir.summary.text
        assert len(ir.education) == 1
        assert len(ir.certifications) == 1

    def test_only_selected_entries_lifted(self):
        ir = _selection_ir()
        assert [e.id for e in ir.experience] == ["1"]
        assert [p.id for p in ir.projects] == ["4"]

    def test_bullets_carry_provenance_and_importance(self):
        ir = _selection_ir()
        exp = ir.experience[0]
        assert exp.bullets[0].evidence_ids == ["exp-1-b0"]
        python_id = REQUIREMENTS[0].id
        xgb_id = REQUIREMENTS[1].id
        docs, xgb = exp.bullets
        assert docs.requirement_ids == []
        assert docs.importance == 0.0
        assert xgb_id in xgb.requirement_ids
        assert xgb.importance == 0.95
        assert python_id in ir.projects[0].bullets[0].requirement_ids
        # Kubernetes has no evidence anywhere
        assert all(
            REQUIREMENTS[2].id not in b.requirement_ids
            for b in ir.all_bullets()
        )

    def test_skills_grouped_by_master_category(self):
        ir = _selection_ir()
        assert ir.skills.categories == {"ml": ["XGBoost"], "core": ["Python"]}

    def test_no_requirements_all_zero_importance(self):
        ir = ir_from_selection(SNAPSHOT, [1], [])
        assert all(b.importance == 0.0 for b in ir.all_bullets())


class TestPlanResume:
    def test_standard_section_order(self):
        plan = plan_resume(_selection_ir(), REQUIREMENTS)
        assert plan.section_order == SECTION_ORDER
        assert plan.page_line_budget == PAGE_LINE_BUDGET
        assert plan.over_budget is False

    def test_bullets_reordered_by_importance(self):
        plan = plan_resume(_selection_ir(), REQUIREMENTS)
        exp = plan.ir.experience[0]
        # XGBoost bullet (0.95) outranks the docs bullet (0.0)
        assert exp.bullets[0].importance == 0.95
        assert "XGBoost" in exp.bullets[0].text

    def test_zero_importance_keeps_original_order(self):
        ir = ir_from_selection(SNAPSHOT, [1, 2], [])
        plan = plan_resume(ir, [])
        assert [b.text for b in plan.ir.experience[0].bullets] == [
            "Wrote internal docs", "Built XGBoost ranking model 15%",
        ]

    @staticmethod
    def _bulky_ir() -> ResumeIR:
        return ResumeIR(
            header=HeaderIR(name="X"),
            experience=[
                ExperienceIR(
                    id="1", title="T", organization="O",
                    bullets=[
                        ResumeBullet(text=f"bullet {i}", space_cost=1,
                                     importance=0.9 if i == 0 else 0.0)
                        for i in range(4)
                    ],
                )
            ],
        )

    def test_budget_drops_lowest_importance_bullets(self):
        # space = 4 bullets + 3 header + 2 entry = 9; budget 7 -> drop 2
        plan = plan_resume(self._bulky_ir(), page_lines=7)
        assert plan.estimated_lines <= 7
        assert plan.over_budget is False
        assert len(plan.dropped) == 2
        assert [b.text for b in plan.ir.experience[0].bullets] == [
            "bullet 0", "bullet 1",
        ]
        assert plan.dropped == ["experience-1:b3", "experience-1:b2"]

    def test_projects_drop_before_experience_on_tie(self):
        ir = self._bulky_ir()
        from applyjin.resume.ir import ProjectIR

        ir.projects.append(
            ProjectIR(id="9", name="P", bullets=[
                ResumeBullet(text="p0", space_cost=1, importance=0.0),
            ])
        )
        # space = 5 bullets + 3 header + 2 exp + 2 prj = 12; the project
        # drop also removes its entry header (-2) -> 9 <= 10, done.
        plan = plan_resume(ir, page_lines=10)
        assert plan.dropped == ["project-9:b0"]

    def test_entry_removed_when_all_bullets_dropped(self):
        ir = self._bulky_ir()
        ir.experience[0].bullets = [
            ResumeBullet(text="low", space_cost=1, importance=0.0)
            for _ in range(3)
        ]
        # space = 3 + 3 + 2 = 8; budget 2 -> all bullets go, entry empties,
        # and the fixed header (3) alone still exceeds the budget.
        plan = plan_resume(ir, page_lines=2)
        assert plan.ir.experience == []
        assert plan.over_budget is True

    def test_generous_budget_drops_nothing(self):
        plan = plan_resume(_selection_ir(), REQUIREMENTS)
        assert plan.dropped == []

    def test_plan_json_round_trip(self):
        plan = plan_resume(_selection_ir(), REQUIREMENTS)
        again = ResumePlan.model_validate_json(plan.model_dump_json())
        assert again == plan


class TestFixedSectionCaps:
    def test_certs_capped_with_coverage_priority(self):
        ir = ResumeIR(header=HeaderIR(name="X"))
        ir.certifications = [
            CertificationIR(name=f"Cert {i}") for i in range(5)
        ]
        ir.certifications.append(
            CertificationIR(name="AWS Solutions Architect")
        )
        reqs = [make_requirement("Experience with AWS")]
        plan = plan_resume(ir, reqs, page_lines=46)
        names = [c.name for c in plan.ir.certifications]
        assert len(names) == 3
        assert "AWS Solutions Architect" in names  # covered cert survives
        assert sum(1 for d in plan.dropped if d.startswith("certifications-")) == 3

    def test_education_capped(self):
        ir = ResumeIR(header=HeaderIR(name="X"))
        ir.education = [
            EducationIR(degree=f"Deg {i}") for i in range(4)
        ]
        plan = plan_resume(ir, [], page_lines=46)
        assert len(plan.ir.education) == 2
        assert "education-2" in plan.dropped
        assert "education-3" in plan.dropped

    def test_summary_trimmed_at_word_boundary(self):
        ir = ResumeIR(header=HeaderIR(name="X"))
        from applyjin.resume.ir import SummaryIR

        ir.summary = SummaryIR(text=" ".join(["word"] * 60))
        plan = plan_resume(ir, [], page_lines=46)
        assert len(ir.summary.text.split()) == 4 * 11
        assert "summary-trimmed" in plan.dropped

    def test_caps_prevent_bullet_massacre(self):
        # 64 certifications used to consume the page and force every
        # bullet to be dropped; caps must keep the bullets alive.
        ir = ResumeIR(header=HeaderIR(name="X"))
        ir.certifications = [
            CertificationIR(name=f"Cert {i}") for i in range(64)
        ]
        ir.experience.append(
            ExperienceIR(
                id="1", title="T", organization="O",
                bullets=[
                    ResumeBullet(text=f"bullet {i}", space_cost=1,
                                 importance=0.9 if i == 0 else 0.0)
                    for i in range(4)
                ],
            )
        )
        plan = plan_resume(ir, [], page_lines=46)
        assert plan.ir.experience[0].bullets  # nothing (or little) dropped
        assert plan.over_budget is False
        assert len(plan.ir.certifications) == 3
