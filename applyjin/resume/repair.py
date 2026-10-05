"""Deterministic one-page repair: a compression hierarchy for markdown.

Used when the final resume (especially free-markdown output) exceeds the
line budget: each `repair_step` applies exactly ONE step of the hierarchy
and returns (markdown, changed). Callers loop until the resume fits or
the steps are exhausted — never shrinking the font, never inventing or
rewriting content:

    1. trim an over-long summary (44-word cap)
    2. drop the lowest-priority trailing bullet of the last project
    3. drop the lowest-priority trailing bullet of the last experience
    4. drop the least-relevant project entry entirely
    5. drop the least-relevant experience entry (never the last one)
    6. remove the summary section
    7. halve the skills line

Bullets are importance-sorted (highest first) by the planner, so the
LAST bullet of an entry and the LAST entry are the correct things to
drop when only the markdown is available.
"""

from __future__ import annotations

import math
import re

from applyjin.resume.ir import WORDS_PER_LINE

# Same cap the planner enforces on summaries.
MAX_SUMMARY_WORDS = 4 * WORDS_PER_LINE

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_ENTRY_RE = re.compile(r"^###\s+")
_BULLET_RE = re.compile(r"^[-*]\s+")


def _section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """section name (lowercase) -> (heading index, exclusive end index)."""
    ranges: dict[str, tuple[int, int]] = {}
    starts: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m:
            starts.append((m.group(1).strip().lower(), i))
    for idx, (name, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
        ranges[name] = (start, end)
    return ranges


def _trim_summary(lines: list[str]) -> tuple[list[str], bool]:
    ranges = _section_ranges(lines)
    if "summary" not in ranges:
        return lines, False
    start, end = ranges["summary"]
    body = [ln for ln in lines[start + 1:end] if ln.strip()]
    text = " ".join(body).strip()
    words = text.split()
    if len(words) <= MAX_SUMMARY_WORDS:
        return lines, False
    trimmed = " ".join(words[:MAX_SUMMARY_WORDS]).rstrip(",;: ")
    return lines[: start + 1] + [trimmed] + lines[end:], True


def _drop_trailing_bullet(
    lines: list[str], section: str, min_bullets: int
) -> tuple[list[str], bool]:
    ranges = _section_ranges(lines)
    if section not in ranges:
        return lines, False
    start, end = ranges[section]
    # Last ### entry inside the section (fallback: whole section).
    entry_starts = [
        i for i in range(start + 1, end) if _ENTRY_RE.match(lines[i])
    ]
    block_start = entry_starts[-1] if entry_starts else start + 1
    bullets = [
        i for i in range(block_start, end) if _BULLET_RE.match(lines[i])
    ]
    if len(bullets) < min_bullets:
        return lines, False
    victim = bullets[-1]
    return lines[:victim] + lines[victim + 1:], True


def _drop_last_entry(
    lines: list[str], section: str, min_entries: int
) -> tuple[list[str], bool]:
    ranges = _section_ranges(lines)
    if section not in ranges:
        return lines, False
    start, end = ranges[section]
    entry_starts = [
        i for i in range(start + 1, end) if _ENTRY_RE.match(lines[i])
    ]
    if len(entry_starts) < min_entries:
        return lines, False
    block_start = entry_starts[-1]
    # Entry block runs to the section end; strip trailing blank lines.
    block_end = end
    while block_end > block_start and not lines[block_end - 1].strip():
        block_end -= 1
    remainder = lines[start + 1:block_start] + lines[block_end:end]
    if not any(line.strip() for line in remainder):
        # Section would be empty — remove the heading too.
        heading = start
        if heading > 0 and not lines[heading - 1].strip():
            heading -= 1
        return lines[:heading] + lines[block_end:], True
    return lines[:block_start] + lines[block_end:], True


def _remove_summary(lines: list[str]) -> tuple[list[str], bool]:
    ranges = _section_ranges(lines)
    if "summary" not in ranges:
        return lines, False
    start, end = ranges["summary"]
    # Also swallow one preceding blank line.
    if start > 0 and not lines[start - 1].strip():
        start -= 1
    return lines[:start] + lines[end:], True


def _halve_skills(lines: list[str]) -> tuple[list[str], bool]:
    ranges = _section_ranges(lines)
    if "skills" not in ranges:
        return lines, False
    start, end = ranges["skills"]
    for i in range(start + 1, end):
        if lines[i].strip() and not _HEADING_RE.match(lines[i]):
            names = [n.strip() for n in lines[i].split(",") if n.strip()]
            if len(names) <= 4:
                return lines, False
            keep = max(4, math.ceil(len(names) / 2))
            lines[i] = ", ".join(names[:keep])
            return lines, True
    return lines, False


_STEPS = (
    _trim_summary,
    lambda ls: _drop_trailing_bullet(ls, "projects", min_bullets=2),
    lambda ls: _drop_trailing_bullet(ls, "experience", min_bullets=2),
    lambda ls: _drop_last_entry(ls, "projects", min_entries=1),
    lambda ls: _drop_last_entry(ls, "experience", min_entries=2),
    _remove_summary,
    _halve_skills,
)


def repair_step(md: str) -> tuple[str, bool]:
    """Apply the next compression step. (markdown, changed)."""
    lines = md.splitlines()
    for step in _STEPS:
        new_lines, changed = step(lines)
        if changed:
            return "\n".join(new_lines).strip() + "\n", True
    return md, False


def compress_to_fit(md: str, estimate, budget: int, max_steps: int = 12) -> str:
    """Apply repair steps until the estimate fits the budget (best effort)."""
    for _ in range(max_steps):
        if estimate(md) <= budget:
            return md
        md, changed = repair_step(md)
        if not changed:
            break
    return md
