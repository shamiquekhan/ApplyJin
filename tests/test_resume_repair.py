"""One-page repair: compression hierarchy for markdown output."""

from __future__ import annotations

from hermes.resume.repair import compress_to_fit, repair_step
from hermes.resume.render import estimate_md_lines

LONG_SUMMARY = " ".join(["word"] * 60)

BASE_MD = """# Jane Doe
jane@x.com

## Summary
AI engineer focused on RAG pipelines

## Experience
### SWE | Acme | 2020 - Present
- First experience bullet
- Second experience bullet
- Third experience bullet

## Projects
### RAG Agent — Python
- Project bullet one
- Project bullet two

## Skills
Python, FastAPI, Docker, LangChain, RAG, PyTorch, SQL, Git
"""


def _summary_words(md: str) -> list[str]:
    body = md.split("## Summary\n", 1)[1].split("\n", 1)[0]
    return body.split()


class TestRepairStep:
    def test_long_summary_trims_first_at_word_cap(self):
        md = BASE_MD.replace("AI engineer focused on RAG pipelines", LONG_SUMMARY)
        out, changed = repair_step(md)
        assert changed
        assert len(_summary_words(out)) == 44
        assert "## Experience" in out  # nothing else touched

    def test_project_bullet_dropped_before_project_entry(self):
        out, changed = repair_step(BASE_MD)
        assert changed
        assert "Project bullet two" not in out
        assert "Project bullet one" in out
        assert "### RAG Agent" in out  # entry still present

    def test_empty_section_heading_removed_with_entry(self):
        md = BASE_MD.replace("- Project bullet one\n", "").replace(
            "- Project bullet two\n", ""
        )
        md = md.replace("- Second experience bullet\n", "").replace(
            "- Third experience bullet\n", ""
        )
        # Single-bullet experience and bullet-less project: the first
        # applicable step is dropping the empty project entry — its
        # heading must not linger.
        out, changed = repair_step(md)
        assert changed
        assert "### RAG Agent" not in out
        assert "## Projects" not in out
        assert "### SWE" in out

    def test_never_drops_the_last_experience_entry(self):
        md = (
            "# Jane Doe\n\n## Experience\n### SWE | Acme | 2020 - Present\n"
            "- only bullet\n"
        )
        cur = md
        for _ in range(20):
            cur, changed = repair_step(cur)
            if not changed:
                break
        assert "## Experience" in cur
        assert "### SWE" in cur

    def test_noop_when_nothing_to_repair(self):
        md = "# Jane Doe\n\n## Experience\n### SWE | Acme\n- one bullet\n"
        out, changed = repair_step(md)
        assert not changed
        assert out == md

    def test_skills_line_halved_last(self):
        md = (
            "# Jane Doe\n\n## Experience\n### SWE | Acme\n- one bullet\n\n"
            "## Skills\nPython, FastAPI, Docker, LangChain, RAG, PyTorch, SQL, Git\n"
        )
        # Burn through the higher-priority steps first.
        cur = md
        for _ in range(12):
            cur, changed = repair_step(cur)
            if not changed:
                break
        skills = cur.split("## Skills\n", 1)[1].split("\n", 1)[0]
        names = [n for n in skills.split(",") if n.strip()]
        assert len(names) <= 4


class TestCompressToFit:
    def test_monotone_and_fits_when_possible(self):
        # ~60 estimated lines; budget 30 must be reachable by repairs.
        bullets = "\n".join(f"- bullet number {i} with enough words" for i in range(30))
        md = (
            "# Jane Doe\n\n## Summary\n" + LONG_SUMMARY + "\n\n"
            "## Experience\n### SWE | Acme | 2020 - Present\n" + bullets + "\n"
        )
        start = estimate_md_lines(md)
        out = compress_to_fit(md, estimate_md_lines, 30, max_steps=12)
        end = estimate_md_lines(out)
        assert start > 30
        assert end <= start
        assert end <= 30  # reachable within 12 steps

    def test_best_effort_when_exhausted(self):
        bullets = "\n".join(f"- filler bullet line {i} here" for i in range(60))
        md = (
            "# Jane Doe\n\n## Experience\n### SWE | Acme | 2020 - Present\n"
            + bullets + "\n"
        )
        out = compress_to_fit(md, estimate_md_lines, 5, max_steps=2)
        assert estimate_md_lines(out) <= estimate_md_lines(md)
