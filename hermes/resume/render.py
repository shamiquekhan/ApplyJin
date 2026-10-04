"""Deterministic ResumeIR -> Markdown renderer.

One output format for every path (planned fallback, IR-composed, and the
guardrail evidence), so validation and claim verification always see the
same structure:

    # Name / contact line
    ## Summary | ## Experience (### Title | Org | dates) | ## Projects
    ## Skills | ## Education | ## Certifications

Section names are ATS-standard; experience lines use the pipe format the
organization guardrail parses.
"""

from __future__ import annotations

from hermes.resume.ir import ExperienceIR, ProjectIR, ResumeIR


def _experience_line(entry: ExperienceIR) -> str:
    bits = [entry.title, entry.organization]
    dates = " - ".join(d for d in (entry.start_date, entry.end_date) if d)
    if dates:
        bits.append(dates)
    line = " | ".join(b for b in bits if b)
    if not line:
        return ""
    if entry.location:
        line += f" | {entry.location}"
    return f"### {line}"


def _project_line(entry: ProjectIR) -> str:
    if entry.tech:
        return f"### {entry.name} — {entry.tech}"
    return f"### {entry.name}" if entry.name else ""


def render_markdown(ir: ResumeIR) -> str:
    """Render the IR as markdown. Deterministic: same IR -> same bytes."""
    parts: list[str] = []

    if ir.header.name:
        parts.append(f"# {ir.header.name}")
        contact = " | ".join(
            p for p in (
                ir.header.location, ir.header.email, ir.header.linkedin,
                ir.header.github, ir.header.website,
            ) if p
        )
        if contact:
            parts.append(contact)

    if ir.summary and ir.summary.text.strip():
        parts += ["", "## Summary", ir.summary.text.strip()]

    if ir.experience:
        parts += ["", "## Experience"]
        for entry in ir.experience:
            parts.append(_experience_line(entry))
            if entry.description:
                parts.append(entry.description)
            parts += [f"- {b.text}" for b in entry.bullets]

    if ir.projects:
        parts += ["", "## Projects"]
        for entry in ir.projects:
            parts.append(_project_line(entry))
            if entry.description:
                parts.append(entry.description)
            parts += [f"- {b.text}" for b in entry.bullets]
            if entry.link:
                parts.append(entry.link)

    skills_flat = [
        name for names in ir.skills.categories.values() for name in names
    ]
    if skills_flat:
        parts += ["", "## Skills", ", ".join(skills_flat)]

    if ir.education:
        parts += ["", "## Education"]
        for edu in ir.education:
            bits = [edu.degree, edu.institution, edu.end_date]
            line = " | ".join(b for b in bits if b)
            if line:
                parts.append(f"- {line}")

    if ir.certifications:
        parts += ["", "## Certifications"]
        for cert in ir.certifications:
            bits = [cert.name, cert.issuer, cert.date]
            line = " · ".join(b for b in bits if b)
            if line:
                parts.append(f"- {line}")

    return "\n".join(parts).strip() + "\n"
