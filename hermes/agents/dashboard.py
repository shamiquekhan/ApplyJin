"""Terminal dashboard: funnel, review queue, follow-ups, A/B verdict.

Read-only view over the tracker + learning data. Rich-powered, so it
works over SSH and in CI logs alike.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from hermes.agents.ab_testing import analyze_variants
from hermes.agents.learning_agent import LearningAgent
from hermes.agents.tracker import Tracker

console = Console()

_FOLLOWUP_AFTER_DAYS = 7

_STAGE_ORDER = [
    "pending_review", "approved", "submitted", "no_response",
    "rejected", "phone_screen", "interview", "offer",
]
_STAGE_LABELS = {
    "pending_review": "Pending review",
    "approved": "Approved (to submit)",
    "submitted": "Submitted",
    "no_response": "No response",
    "rejected": "Rejected",
    "phone_screen": "Phone screen",
    "interview": "Interview",
    "offer": "Offer",
}


def _bar(count: int, max_count: int, width: int = 24) -> str:
    if max_count == 0:
        return ""
    filled = int(round(count / max_count * width))
    return "█" * filled + "░" * (width - filled)


def render(
    db_path: Path = Path("data/hermes.db"),
    days: int = 30,
    learning: bool = True,
) -> None:
    """Print the full dashboard to the terminal."""
    tracker = Tracker(db_path)
    try:
        records = tracker.list_applications(days=days)
        stats = tracker.stats(days=days)
    finally:
        tracker.close()

    if not records:
        console.print(
            Panel(
                "[dim]No applications yet. Run [bold]hermes run[/bold] "
                "to start the pipeline.[/dim]",
                title="Hermes Dashboard",
            )
        )
        return

    cutoff = datetime.utcnow() - timedelta(days=days)
    window = [r for r in records if (r.applied_at or datetime.utcnow()) >= cutoff]

    # ------------------------------------------------------- header
    console.print(
        Panel(
            f"[bold]{len(window)} applications in the last {days} days[/bold] "
            f"· response rate [green]{stats['response_rate']:.0%}[/green] "
            f"· interview rate [cyan]{stats['interview_rate']:.0%}[/cyan]",
            title="Hermes Dashboard",
        )
    )

    # ------------------------------------------------------- funnel
    by_status: dict[str, int] = {}
    for record in window:
        by_status[record.status] = by_status.get(record.status, 0) + 1
    max_count = max(by_status.values()) if by_status else 1
    funnel = Table(title="Pipeline Funnel", show_header=False, box=None)
    funnel.add_column("stage", style="cyan", width=20)
    funnel.add_column("count", justify="right")
    funnel.add_column("bar")
    for stage in _STAGE_ORDER:
        count = by_status.get(stage, 0)
        if count or stage in ("submitted", "offer"):
            label = _STAGE_LABELS[stage]
            color = (
                "green" if stage in ("interview", "offer") else
                "yellow" if stage in ("phone_screen", "approved") else "white"
            )
            funnel.add_row(
                label, str(count), Text(_bar(count, max_count), style=color)
            )
    console.print(funnel)

    # ------------------------------------------------------- review queue
    pending = [r for r in window if r.status == "pending_review"]
    if pending:
        queue = Table(title=f"Review Queue ({len(pending)}) — run: hermes review")
        for col in ("id", "fit", "ATS", "title", "company"):
            queue.add_column(col)
        for record in pending[:8]:
            ats = (
                f"{record.ats_score_before:.0%}→{record.ats_score_after:.0%}"
                if record.ats_score_before is not None
                else "-"
            )
            queue.add_row(
                str(record.id), f"{record.fit_score:.2f}", ats,
                record.title[:32], record.company[:18],
            )
        console.print(queue)
        if len(pending) > 8:
            console.print(f"  [dim]...and {len(pending) - 8} more[/dim]")

    # ------------------------------------------------------- follow-ups
    now = datetime.utcnow()
    followups = [
        r for r in window
        if r.status in ("submitted", "no_response")
        and r.applied_at
        and (now - r.applied_at).days >= _FOLLOWUP_AFTER_DAYS
    ]
    if followups:
        fup = Table(title=f"Follow-ups due ({len(followups)}) — draft: hermes outreach --id <id>")
        for col in ("id", "applied", "days", "title", "company"):
            fup.add_column(col)
        for record in sorted(followups, key=lambda r: r.applied_at)[:8]:
            fup.add_row(
                str(record.id),
                record.applied_at.strftime("%m-%d"),
                str((now - record.applied_at).days),
                record.title[:32], record.company[:18],
            )
        console.print(fup)

    # ------------------------------------------------------- A/B verdict
    tracker = Tracker(db_path)
    try:
        variant_stats = tracker.variant_stats()
    finally:
        tracker.close()
    if variant_stats.get("A") or variant_stats.get("B"):
        result = analyze_variants(variant_stats)
        style = "green" if result.winner != "inconclusive" else "dim"
        console.print(
            Panel(
                Text(result.summary(), style=style),
                title="A/B Test — resume variants",
            )
        )

    # ------------------------------------------------------- style guide
    if learning:
        tracker = Tracker(db_path)
        try:
            version, guide = tracker.active_style_guide()
        finally:
            tracker.close()
        if version is not None:
            console.print(
                Panel(
                    Text(guide.splitlines()[0] if guide else "", style="cyan"),
                    title=f"Active Style Guide (v{version}) — hermes learn to refresh",
                )
            )
        else:
            console.print(
                Panel(
                    "[dim]No style guide yet — run [bold]hermes learn --apply[/bold] "
                    "after ~30 outcomes.[/dim]",
                    title="Learning",
                )
            )
