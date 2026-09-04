"""Seed the tracker with realistic synthetic outcomes to demo the learning loop.

Creates 50 applications across 8 companies with tailored resume files,
A/B variants, ATS deltas, and plausible outcome timelines — enough data
for the Learning Agent to produce a real style guide. For testing only:
`python scripts/seed_demo_data.py --wipe` resets first.

The synthetic data encodes a learnable signal by design:
- Variant B (metric-led bullets) gets interviews at ~2x the rate of A
- Resumes containing "RAG" / "LangGraph" / metrics correlate with callbacks
This lets `hermes learn` genuinely discover and promote the better pattern.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.tracker import Tracker  # noqa: E402
from hermes.models import ApplicationRecord  # noqa: E402

COMPANIES = [
    "AgentCo", "LLMLabs", "VectorWorks", "PromptCraft", "EmbedCorp",
    "ChainOfThought AI", "RetrievalHQ", "TokenFlow",
]

# Skill templates: variant A = plain phrasing, B = metric-led phrasing.
BULLET_A = (
    "- Built {skill} pipelines in Python for production services\n"
    "- Collaborated with teams on {skill} integrations\n"
    "- Maintained documentation for {skill} workflows\n"
)
BULLET_B = (
    "- Built {skill} pipelines in Python handling 2M+ requests/day, cutting latency 30%\n"
    "- Led {skill} integration adopted by 3 teams, improving throughput 40%\n"
    "- Reduced {skill} deployment time by 70% via automation\n"
)

SKILLS = ["RAG", "LangGraph", "FastAPI", "PyTorch", "LLM evaluation", "Docker"]


def seed(db_path: Path = Path("data/hermes.db"), wipe: bool = False) -> None:
    if wipe and db_path.exists():
        db_path.unlink()
    tracker = Tracker(db_path)
    rng = random.Random(42)

    now = datetime.utcnow()
    created = 0
    for company in COMPANIES:
        for i in range(1, 7):
            variant = "A" if (i % 2 == 0) else "B"
            skill = rng.choice(SKILLS)
            template = BULLET_A if variant == "A" else BULLET_B
            resume_md = (
                f"# Shamique Khan\n\n## Experience\n\n"
                f"### {company} Project {i}\n\n"
                + template.format(skill=skill)
            )

            app_dir = Path("data/applications") / f"demo-{company.lower()}-{i:02d}"
            app_dir.mkdir(parents=True, exist_ok=True)
            resume_path = app_dir / "resume.md"
            resume_path.write_text(resume_md, encoding="utf-8")

            applied = now - timedelta(days=rng.randint(7, 30))
            ats_before = round(rng.uniform(0.35, 0.5), 3)
            ats_after = round(
                min(0.95, ats_before + rng.uniform(0.05, 0.25)), 3
            )

            # Encoded signal: B interviews at a decisively higher rate.
            interview_p = 0.50 if variant == "B" else 0.14
            if rng.random() < interview_p:
                status = rng.choice(["interview", "phone_screen"])
            elif rng.random() < 0.4:
                status = "rejected"
            else:
                status = "no_response"

            record = ApplicationRecord(
                job_id=f"demo-{company.lower()}-{i:02d}",
                title=f"{skill} Engineer",
                company=company,
                board="demo",
                url=f"https://example.com/{company.lower()}/{i}",
                applied_at=applied,
                status=status,
                fit_score=round(rng.uniform(0.55, 0.85), 3),
                ats_score_before=ats_before,
                ats_score_after=ats_after,
                resume_variant_hash=f"hash-{company}-{i}",
                coverletter_hash=f"clhash-{company}-{i}",
                tailored_resume_path=str(resume_path),
                coverletter_path="",
                notes=f"matched: {skill}, Python | variant={variant} (seeded)",
                variant=variant,
            )
            row_id, _ = tracker.add_application(record)
            if row_id:
                # add_application defaults status to record.status via insert;
                # ensure final status set after insert.
                tracker.conn.execute(
                    "UPDATE applications SET status = ? WHERE id = ?",
                    (status, row_id),
                )
                tracker.conn.execute(
                    "UPDATE applications SET applied_at = ? WHERE id = ?",
                    (applied, row_id),
                )
                created += 1
    tracker.conn.commit()
    tracker.close()
    print(f"Seeded {created} synthetic applications with outcomes.")
    print("Run: .venv/bin/hermes learn --verbose")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="Reset DB first")
    args = parser.parse_args()
    seed(wipe=args.wipe)
