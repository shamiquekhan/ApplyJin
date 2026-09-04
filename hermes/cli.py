"""Hermes CLI (Typer + Rich): run, scout, tailor, review, tracker."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from hermes import __version__
from hermes.config import (
    Profile,
    SearchEntry,
    load_profile,
    load_search_configs,
)
from hermes.models import JobPosting
from hermes.utils.llm_router import LLMRouter, LLMUnavailable, make_router

app = typer.Typer(
    name="hermes",
    help="Self-learning job application agent. Auto-tailor + auto-fill, human clicks submit.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
tracker_app = typer.Typer(help="Application tracker commands.")
app.add_typer(tracker_app, name="tracker")

console = Console()
err_console = Console(stderr=True)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _router_or_none() -> Optional[LLMRouter]:
    router = make_router()
    return router if router.available else None


@app.callback()
def _main(
    verbose: bool = typer.Option(False, "--verbose", help="Debug logging"),
    profile: str = typer.Option(
        "default", "--profile", "-p",
        help="Named profile from config/profiles/ (see hermes profiles)",
    ),
) -> None:
    from hermes.config import load_dotenv

    load_dotenv()
    _setup_logging(verbose)
    _PROFILE_NAME["value"] = profile


_PROFILE_NAME: dict = {"value": "default"}


def _load_profile_for_cli() -> Profile:
    from hermes.config import load_profile

    try:
        return load_profile(name=_PROFILE_NAME["value"])
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


# ------------------------------------------------------------------ run


@app.command()
def run(
    offline: bool = typer.Option(
        False, "--offline", help="Use data/sample_jobs.jsonl instead of live scrape"
    ),
    title: Optional[str] = typer.Option(None, help="Override search title"),
    location: Optional[str] = typer.Option(None, help="Override location"),
    limit: Optional[int] = typer.Option(None, help="Max jobs to process"),
    resume: Optional[Path] = typer.Option(
        None, "--resume", help="Path to base resume (md/txt/pdf)"
    ),
) -> None:
    """Full pipeline: scout -> analyze -> score -> tailor -> track for review."""
    from hermes.orchestrator import Orchestrator

    profile = _load_profile_for_cli()
    router = _router_or_none()
    if router is None:
        console.print(
            "[yellow]No LLM configured — running in heuristic mode "
            "(JD analysis via lexicon, template cover letters, base resume as-is).[/yellow]"
        )

    try:
        orch = Orchestrator(
            router=router, base_resume_path=resume, profile=profile
        )
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    search = None
    if title:
        profile = orch.profile
        search = SearchEntry(
            name="cli",
            title=title,
            location=location or profile.identity.location or "Remote",
            boards=profile.preferences.boards,
            max_results=profile.preferences.max_results_per_board,
            hours_old=profile.preferences.max_age_days * 24,
            remote_only=profile.preferences.remote_only,
        )

    with console.status("[bold green]Running pipeline..."):
        result = orch.run(search=search, offline=offline, limit=limit)

    table = Table(title="Pipeline Run")
    table.add_column("Stage", style="cyan")
    table.add_column("Count", justify="right", style="green")
    for label, value in (
        ("Discovered", result.discovered),
        ("Analyzed", result.analyzed),
        ("Passed fit filter", result.passed_filter),
        ("Tailored", result.tailored),
        ("Tracked (pending review)", result.tracked),
        ("Skipped", len(result.skipped)),
        ("Blocked", len(result.blocked)),
    ):
        table.add_row(label, str(value))
    console.print(table)

    for note in result.skipped[:10]:
        console.print(f"  [dim]skip: {note}[/dim]")
    for note in result.blocked:
        console.print(f"  [yellow]blocked: {note}[/yellow]")

    if result.tracked:
        console.print(
            f"\n[bold green]{result.tracked} application(s) queued.[/bold green] "
            "Run [bold]hermes review[/bold] to approve/reject each one."
        )
    else:
        console.print("\n[dim]Nothing new to review.[/dim]")


# ------------------------------------------------------------------ scout


@app.command()
def scout(
    title: str = typer.Option("Software Engineer", help="Search term"),
    location: str = typer.Option("Remote", help="Location"),
    boards: str = typer.Option(
        "indeed,glassdoor,google", help="Comma-separated boards"
    ),
    max_results: int = typer.Option(40, help="Results per board"),
    offline: bool = typer.Option(False, "--offline", help="Use sample jobs"),
    ats: Optional[str] = typer.Option(
        None, "--ats",
        help="Company slug(s) for Greenhouse/Lever boards (comma-separated)",
    ),
    save: Optional[Path] = typer.Option(
        None, "--save", help="Save results as JSONL (e.g. data/sample_jobs.jsonl)"
    ),
) -> None:
    """Discover jobs (discovery only — no tracking, no tailoring)."""
    from hermes.agents.job_scout import scout_jobs

    if ats:
        from hermes.agents.ats_scout import scrape_at_boards

        companies = [c.strip() for c in ats.split(",") if c.strip()]
        with console.status("[bold green]Querying ATS boards..."):
            jobs = scrape_at_boards(companies, keywords=title if title != "Software Engineer" else None)
        if not jobs:
            console.print(
                "[yellow]No postings found — check the company slug "
                "(e.g. from boards.greenhouse.io/COMPANY/jobs).[/yellow]"
            )
            return
    else:
        entry = SearchEntry(
            name="cli-scout",
            title=title,
            location=location,
            boards=[b.strip() for b in boards.split(",") if b.strip()],
            max_results=max_results,
        )
        with console.status("[bold green]Scraping boards..."):
            jobs = scout_jobs(entry, offline=offline)

    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(title=f"{len(jobs)} unique jobs — {title} @ {location}")
    for col in ("#", "Title", "Company", "Board", "Location"):
        table.add_column(col)
    for i, job in enumerate(jobs[:25], 1):
        table.add_row(str(i), job.title[:45], job.company[:25], job.board, job.location[:20])
    console.print(table)
    if len(jobs) > 25:
        console.print(f"[dim]...and {len(jobs) - 25} more[/dim]")

    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        with open(save, "w", encoding="utf-8") as fh:
            for job in jobs:
                fh.write(job.model_dump_json() + "\n")
        console.print(f"[green]Saved {len(jobs)} jobs to {save}[/green]")


# ------------------------------------------------------------------ tailor


@app.command()
def tailor(
    title: str = typer.Option(..., help="Job title"),
    company: str = typer.Option("Example Corp", help="Company name"),
    description_file: Path = typer.Option(
        ..., "--description-file", help="Path to JD text/markdown file"
    ),
    resume: Optional[Path] = typer.Option(None, "--resume", help="Base resume path"),
) -> None:
    """Dry-run: analyze + tailor + cover letter for one JD (no tracker writes)."""
    from hermes.agents.cover_letter import CoverLetterAgent
    from hermes.agents.fit_scorer import FitScorer
    from hermes.agents.jd_analyzer import JDAnalyzer
    from hermes.agents.resume_tailor import ResumeTailor
    from hermes.orchestrator import find_base_resume
    from hermes.utils.resume_parser import parse_resume

    if not description_file.exists():
        err_console.print(f"[red]No such file: {description_file}[/red]")
        raise typer.Exit(1)

    profile = load_profile()
    router = _router_or_none()
    resume_path = resume or find_base_resume()
    if resume_path is None:
        err_console.print("[red]No base resume found (data/base_resume.md).[/red]")
        raise typer.Exit(1)

    parsed = parse_resume(resume_path, profile)
    job = JobPosting(
        job_id="dry-run",
        title=title,
        company=company,
        description=description_file.read_text(encoding="utf-8"),
    )

    analysis = JDAnalyzer(router).analyze(job)
    scored = FitScorer(profile, profile.limits.min_fit_score).score(job, analysis, parsed)
    tailored = ResumeTailor(router).tailor(parsed, job, analysis)
    letter = CoverLetterAgent(profile, router).generate(analysis, tailored)

    console.print(Panel(f"[bold]{title}[/bold] @ {company}", title="Analysis"))
    _print_analysis(analysis)
    console.print(
        f"fit_score: [bold]{scored.fit_score}[/bold] "
        f"(passed={scored.passed_filter})\n"
        f"breakdown: {json.dumps({k: v for k, v in scored.score_breakdown.items() if not isinstance(v, list)})}"
    )
    console.print(Panel(tailored.markdown[:3000], title="Tailored Resume"))
    if tailored.guardrail_violations:
        console.print(f"[red]guardrail violations: {tailored.guardrail_violations}[/red]")
    console.print(Panel(letter.text, title=f"Cover Letter ({letter.word_count} words)"))


def _print_analysis(analysis) -> None:
    console.print(
        f"required: {', '.join(analysis.required_skills) or '-'}\n"
        f"seniority: {analysis.seniority_level} | years: {analysis.years_experience} | "
        f"remote: {analysis.remote_policy} | extractor: {analysis.extractor}\n"
        f"red flags: {', '.join(analysis.red_flags) or '-'}"
    )


# ------------------------------------------------------------------ review


@app.command()
def review(
    decision: Optional[str] = typer.Option(
        None, "--decision", help="approve|reject for all pending (skip interactive)"
    ),
) -> None:
    """Human checkpoint: approve/reject/skip each pending application."""
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    pending = tracker.list_applications(status="pending_review")

    if not pending:
        tracker.close()
        console.print("[dim]No applications pending review.[/dim]")
        return

    if decision and decision not in ("approve", "reject"):
        err_console.print("[red]--decision must be approve or reject[/red]")
        tracker.close()
        raise typer.Exit(1)

    approved = rejected = 0
    for record in pending:
        _show_pending(record)
        if decision:
            choice = "a" if decision == "approve" else "r"
        else:
            choice = Prompt.ask(
                "[bold]Decision[/bold]", choices=["a", "r", "s"], default="a"
            )
        if choice == "a":
            tracker.update_status(record.id, "approved", "human review passed")
            approved += 1
            console.print("[green]approved — submit manually via the application URL[/green]")
        elif choice == "r":
            tracker.update_status(record.id, "rejected_by_user", "human review rejected")
            rejected += 1
            console.print("[yellow]rejected[/yellow]")
        else:
            console.print("[dim]skipped (still pending)[/dim]")

    tracker.close()
    console.print(f"\n[bold]approved: {approved} | rejected: {rejected}[/bold]")


def _show_pending(record) -> None:
    table = Table(show_header=False, title=f"#{record.id}")
    table.add_column("k", style="cyan")
    table.add_column("v")
    table.add_row("job", f"{record.title} @ {record.company}")
    table.add_row("fit / ATS", f"{record.fit_score} / {record.ats_score_before} -> {record.ats_score_after}")
    table.add_row("resume", record.tailored_resume_path)
    table.add_row("letter", record.coverletter_path)
    table.add_row("url", record.url or "-")
    table.add_row("notes", (record.notes or "")[:200])
    console.print(table)


# ------------------------------------------------------------------ tracker


@tracker_app.command("list")
def tracker_list(
    status: Optional[str] = typer.Option(None, help="Filter by status"),
    days: Optional[int] = typer.Option(None, help="Last N days"),
) -> None:
    """List tracked applications."""
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    records = tracker.list_applications(status=status, days=days)
    tracker.close()

    if not records:
        console.print("[dim]No applications tracked yet. Run [bold]hermes run[/bold] first.[/dim]")
        return

    table = Table(title=f"{len(records)} applications")
    for col in ("id", "status", "fit", "title", "company", "board", "applied"):
        table.add_column(col)
    for r in records:
        table.add_row(
            str(r.id),
            r.status,
            f"{r.fit_score:.2f}",
            r.title[:35],
            r.company[:20],
            r.board,
            (r.applied_at.strftime("%m-%d") if r.applied_at else "-"),
        )
    console.print(table)


@tracker_app.command("stats")
def tracker_stats(
    days: int = typer.Option(30, help="Window in days"),
) -> None:
    """Response funnel for the last N days."""
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    stats = tracker.stats(days=days)
    tracker.close()

    if stats["total"] == 0:
        console.print("[dim]No applications in the window.[/dim]")
        return

    table = Table(title=f"Last {days} days")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("total", str(stats["total"]))
    for status, count in sorted(stats["by_status"].items()):
        table.add_row(f"  {status}", str(count))
    table.add_row("responses", str(stats["responses"]))
    table.add_row("response_rate", f"{stats['response_rate']:.1%}")
    table.add_row("interviews", str(stats["interviews"]))
    table.add_row("interview_rate", f"{stats['interview_rate']:.1%}")
    console.print(table)


@tracker_app.command("update")
def tracker_update(
    id: int = typer.Option(..., help="Application row id"),
    status: str = typer.Option(..., help="New status"),
    notes: str = typer.Option("", help="Optional notes"),
) -> None:
    """Update application status (e.g. after hearing back)."""
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    try:
        if not tracker.update_status(id, status, notes):
            console.print(f"[red]No application with id={id}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Updated #{id} -> {status}[/green]")
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    finally:
        tracker.close()


# ------------------------------------------------------------------ learn


@app.command()
def learn(
    apply: bool = typer.Option(
        False, "--apply", help="Activate the new style guide (versioned)"
    ),
    min_sample: int = typer.Option(
        30, "--min-sample", help="Minimum outcome records for full confidence"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show full style guide"),
) -> None:
    """Analyze outcomes, discover winning patterns, build a style guide."""
    from hermes.agents.learning_agent import LearningAgent
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    try:
        agent = LearningAgent(tracker, min_sample=min_sample)
        report = agent.analyze()

        panel_lines = report.summary_lines()
        if report.sufficient_data:
            verdict = "[green]sufficient data — style guide is reliable[/green]"
        else:
            verdict = "[yellow]insufficient data — guide is a hypothesis[/yellow]"
        console.print(
            Panel(
                "\n".join(panel_lines) + f"\n\n{verdict}",
                title="Learning Report",
            )
        )
        if verbose and report.style_guide:
            console.print(Panel(report.style_guide, title="Proposed Style Guide"))

        if apply:
            version = agent.apply_style_guide(report)
            console.print(
                f"[green]Style guide v{version} activated. "
                "It will be injected into the tailor prompt on next run.[/green]"
            )
        else:
            console.print(
                "[dim]Dry-run: pass --apply to activate this style guide.[/dim]"
            )
    finally:
        tracker.close()


# ------------------------------------------------------------------ triage


@app.command("triage-email")
def triage_email(
    apply: bool = typer.Option(
        False, "--apply", help="Write status updates to the tracker (default dry-run)"
    ),
) -> None:
    """Scan IMAP inbox for interview/rejection emails, update tracker."""
    from hermes.agents.email_triage import EmailTriageAgent
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    try:
        agent = EmailTriageAgent(tracker)
        try:
            report = agent.triage(apply=apply)
        except FileNotFoundError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        table = Table(title=f"Email Triage ({'APPLY' if apply else 'DRY-RUN'})")
        for col in ("company", "classification", "matched app", "subject"):
            table.add_column(col)
        for m in report.matches:
            table.add_row(
                m.company, m.classification,
                f"#{m.application_id} {m.matched_company} ({m.similarity:.0%})",
                m.subject[:50],
            )
        console.print(table)
        for line in report.summary():
            console.print(f"  {line}")
        if not apply:
            console.print("[dim]Dry-run: pass --apply to update the tracker.[/dim]")
    finally:
        tracker.close()


# -------------------------------------------------------------- dashboard


@app.command()
def dashboard(
    days: int = typer.Option(30, help="Window in days"),
) -> None:
    """Terminal dashboard: funnel, queue, follow-ups, A/B verdict."""
    from hermes.agents.dashboard import render

    render(Path("data/hermes.db"), days=days)


# ------------------------------------------------------------------ prep


@app.command()
def prep(
    id: int = typer.Option(..., help="Application id from hermes tracker list"),
    resume: Optional[Path] = typer.Option(None, "--resume", help="Base resume path"),
) -> None:
    """Generate an interview prep doc (STAR stories + questions) for a job."""
    from hermes.agents.interview_prep import InterviewPrepAgent
    from hermes.agents.jd_analyzer import JDAnalyzer
    from hermes.agents.tracker import Tracker
    from hermes.orchestrator import find_base_resume
    from hermes.utils.experience_library import ExperienceLibrary
    from hermes.utils.resume_parser import parse_resume

    tracker = Tracker(Path("data/hermes.db"))
    try:
        record = tracker.get(id)
    finally:
        tracker.close()
    if record is None:
        err_console.print(f"[red]No application with id={id}[/red]")
        raise typer.Exit(1)

    profile = _load_profile_for_cli()
    resume_path = resume or find_base_resume()
    if resume_path is None:
        err_console.print("[red]No base resume found.[/red]")
        raise typer.Exit(1)
    parsed = parse_resume(resume_path, profile)

    job = JobPosting(
        job_id=record.job_id, title=record.title, company=record.company,
        url=record.url, description="",
    )
    # Rebuild the JD text from the saved job.md artifact when available.
    job_dir = Path(record.tailored_resume_path).parent if record.tailored_resume_path else None
    if job_dir and (job_dir / "job.md").exists():
        job.description = (job_dir / "job.md").read_text(encoding="utf-8")

    router = _router_or_none()
    analysis = JDAnalyzer(router).analyze(job)
    agent = InterviewPrepAgent(
        profile, router, library=ExperienceLibrary()
    )
    out_dir = job_dir if job_dir else None
    out_path = agent.prepare(job, analysis, parsed, output_dir=out_dir)
    console.print(
        f"[green]Interview prep written: {out_path}[/green]\n"
        f"[dim]STAR stories are grounded in your base resume facts only.[/dim]"
    )


# ------------------------------------------------------------------ outreach


@app.command()
def outreach(
    id: int = typer.Option(..., help="Application id"),
) -> None:
    """Draft LinkedIn note + follow-up email (files only — never sends)."""
    from hermes.agents.jd_analyzer import JDAnalyzer
    from hermes.agents.outreach_agent import OutreachAgent
    from hermes.agents.tracker import Tracker
    from hermes.models import JobAnalysis, JobPosting
    from datetime import datetime

    tracker = Tracker(Path("data/hermes.db"))
    try:
        record = tracker.get(id)
    finally:
        tracker.close()
    if record is None:
        err_console.print(f"[red]No application with id={id}[/red]")
        raise typer.Exit(1)

    profile = _load_profile_for_cli()
    job = JobPosting(
        job_id=record.job_id, title=record.title, company=record.company,
        description="",
    )
    router = _router_or_none()
    # Lightweight analysis from title/company when no JD stored.
    analysis = JDAnalyzer(router).analyze(job)

    days_ago = (
        (datetime.utcnow() - record.applied_at).days
        if record.applied_at else 7
    )
    agent = OutreachAgent(profile, router)
    drafts = agent.draft_for(
        analysis, applied_days_ago=max(days_ago, 1),
        output_dir=Path("data/outreach") / record.job_id[:16],
    )
    console.print(
        Panel(drafts["note_text"], title=f"LinkedIn note ({len(drafts['note_text'])}/300 chars)")
    )
    console.print(Panel(drafts["email_text"][:600], title="Follow-up email"))
    console.print(
        f"[green]Saved: {drafts['note']}[/green]\n"
        f"[green]Saved: {drafts['email']}[/green]\n"
        "[yellow]Copy-paste manually — Hermes never sends messages.[/yellow]"
    )


# ------------------------------------------------------------------ serve


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Port"),
) -> None:
    """Run the read-only web dashboard (FastAPI + uvicorn)."""
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        err_console.print(
            "[red]Web extras missing — run: pip install -e '.[web]'[/red]"
        )
        raise typer.Exit(1)

    import uvicorn
    from hermes.web.app import app as web_app

    console.print(
        f"[green]Dashboard: http://{host}:{port}[/green] "
        "[dim](read-only — mutations via CLI)[/dim]"
    )
    uvicorn.run(web_app, host=host, port=port, log_level="warning")


# --------------------------------------------------------------- profiles


@app.command()
def profiles() -> None:
    """List available profiles (config/profiles/*.yml)."""
    from hermes.config import list_profiles

    names = list_profiles()
    current = _PROFILE_NAME["value"]
    table = Table(title="Profiles")
    table.add_column("name", style="cyan")
    table.add_column("active")
    for name in names:
        table.add_row(
            name, "[green]●[/green]" if name == current else ""
        )
    console.print(table)
    console.print(
        "[dim]Use: hermes --profile <name> run  |  "
        "Create: cp config/profile.yml config/profiles/<name>.yml[/dim]"
    )


# ------------------------------------------------------------------ misc


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"hermes {__version__}")


# ------------------------------------------------------------ index-resume


@app.command("index-resume")
def index_resume(
    resume: Optional[Path] = typer.Option(
        None, "--resume", help="Resume path (default: data/base_resume.md)"
    ),
) -> None:
    """Index base resume bullets into the ChromaDB experience library."""
    from hermes.orchestrator import find_base_resume
    from hermes.utils.experience_library import ExperienceLibrary
    from hermes.utils.resume_parser import parse_resume

    resume_path = resume or find_base_resume()
    if resume_path is None:
        err_console.print("[red]No base resume found (data/base_resume.md).[/red]")
        raise typer.Exit(1)

    profile = load_profile()
    parsed = parse_resume(resume_path, profile)
    library = ExperienceLibrary()
    count = library.index_resume(parsed)
    console.print(
        f"[green]Indexed {count} bullets from {resume_path.name} "
        f"(backend: {library.backend})[/green]"
    )
    if count == 0:
        err_console.print(
            "[yellow]No bullets detected — is the resume in markdown with "
            "- bullet lines?[/yellow]"
        )


# ------------------------------------------------------------------ parse


@app.command("parse-resume")
def parse_resume_cmd(
    resume: Path = typer.Option(..., "--resume", "-r", help="Resume file (.docx/.pdf/.md/.txt)"),
    show: bool = typer.Option(False, "--show", help="Print the parsed bullets"),
) -> None:
    """Parse a resume file: extracts text, bullets, skills; shows stats."""
    from hermes.utils.resume_parser import parse_resume

    if not resume.exists():
        err_console.print(f"[red]No such file: {resume}[/red]")
        raise typer.Exit(1)
    profile = _load_profile_for_cli()
    parsed = parse_resume(resume, profile)
    console.print(
        f"[green]Parsed {resume.name}[/green]: "
        f"{len(parsed.bullets)} bullets, {len(parsed.skills)} skills, "
        f"seniority={parsed.seniority}, {parsed.years_experience}y"
    )
    if show:
        for b in parsed.bullets:
            console.print(f"  [dim]-[/dim] {b.text[:100]}")
    console.print(
        "\n[dim]To make it your base resume: copy it to data/base_resume.md "
        "and run hermes index-resume[/dim]"
    )


# ------------------------------------------------------------------ fill


@app.command()
def fill(
    id: int = typer.Option(..., help="Application id from `hermes tracker list`"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Open the page without filling anything"
    ),
    headless: bool = typer.Option(
        False, "--headless", help="Run browser headless (higher detection risk)"
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Non-interactive: don't wait for Enter"
    ),
) -> None:
    """Open the application URL and auto-fill — never submit."""
    from hermes.agents.application_agent import ApplicationAgent
    from hermes.agents.tracker import Tracker

    tracker = Tracker(Path("data/hermes.db"))
    record = tracker.get(id)
    tracker.close()
    if record is None:
        err_console.print(f"[red]No application with id={id}[/red]")
        raise typer.Exit(1)
    if not record.url:
        err_console.print(
            "[red]This application has no URL (offline sample job?).[/red]"
        )
        raise typer.Exit(1)

    resume_pdf = (
        Path(record.tailored_resume_path).with_suffix(".pdf")
        if record.tailored_resume_path
        else None
    )
    if resume_pdf is not None and not resume_pdf.exists():
        resume_pdf = (
            Path(record.tailored_resume_path)
            if record.tailored_resume_path and Path(record.tailored_resume_path).exists()
            else None
        )

    profile = load_profile()
    agent = ApplicationAgent(profile)

    console.print(
        f"[bold]Filling application for {record.title} @ {record.company}[/bold]\n"
        f"URL: {record.url}\n"
        "[yellow]Hermes will STOP before submit — you click it.[/yellow]\n"
    )

    on_pause = (lambda result: None) if yes else None
    result = agent.fill(
        url=record.url,
        job_id=record.job_id,
        resume_path=resume_pdf,
        coverletter_path=record.coverletter_path or None,
        dry_run=dry_run,
        headless=headless,
        on_pause=on_pause,
    )

    table = Table(title=f"Fill Report — #{id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("ATS detected", result.ats_type)
    table.add_row("Fields filled", ", ".join(result.fields_filled) or "-")
    table.add_row("Files uploaded", ", ".join(result.files_uploaded) or "-")
    table.add_row("Submitted", "[red]NO — human clicks submit[/red]")
    table.add_row("Stopped at", result.stopped_at)
    console.print(table)


# ------------------------------------------------------------------ export


@app.command()
def export(
    id: Optional[int] = typer.Option(None, help="Export one application by id"),
    all: bool = typer.Option(False, "--all", help="Export all approved apps"),
) -> None:
    """Regenerate PDFs for tailored resumes (one by id, or all)."""
    from hermes.agents.tracker import Tracker
    from hermes.utils.pdf_generator import generate_pdf

    tracker = Tracker(Path("data/hermes.db"))
    try:
        if id is not None:
            records = [tracker.get(id)]
            records = [r for r in records if r]
            if not records:
                err_console.print(f"[red]No application with id={id}[/red]")
                raise typer.Exit(1)
        elif all:
            records = tracker.list_applications()
        else:
            err_console.print("[red]Pass --id or --all[/red]")
            raise typer.Exit(1)

        for record in records:
            md_path = Path(record.tailored_resume_path)
            if not md_path.exists():
                console.print(f"[yellow]#{record.id}: no resume md at {md_path}[/yellow]")
                continue
            out = generate_pdf(md_path.read_text(encoding="utf-8"), md_path.with_suffix(".pdf"))
            console.print(f"[green]#{record.id}: PDF -> {out}[/green]")
    finally:
        tracker.close()


if __name__ == "__main__":
    app()
