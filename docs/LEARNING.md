# The Learning Loop

## Signals (arrival order)

```
Day 0     Application submitted
Immediate ATS score delta (before vs after tailoring)  — proxy
Day 3-7   Email triage: rejection or interview invite   — medium
Day 7-14  Phone screen / interview scheduled            — high
Day 30+   Offer or final rejection                      — very high
```

Capture: `hermes triage-email --apply` (Gmail/Outlook via IMAP app
password) or manual `hermes tracker update --id N --status interview`.

## What `hermes learn` computes

1. **Keyword lift** — for each skill present in tailored resumes,
   log-odds of appearing in interview-winning vs rejected applications.
   Winning keywords get promoted to "LEAD with ..." in the style guide.
2. **ATS-delta correlation** — Pearson r between tailoring delta and
   interview outcome. Positive: keyword alignment works, front-load JD
   terms. Negative: over-optimization hurts, keep phrasing natural.
3. **A/B chi-squared** — every application is randomly assigned variant
   A (active style guide) or B (experimental). Yates-corrected χ² on
   interview rates decides the winner (p<0.05). A decisive B becomes
   the new active guide via `--apply`.

## Confidence gating

- Full confidence needs ≥30 outcome records and ≥3 interviews
  (`--min-sample` to override). Below that, reports warn and the style
  guide is labeled a hypothesis.
- Style guides are versioned (`style_guide_versions` table). Every
  `--apply` bumps the version and deactivates the previous one — full
  history retained, trivial to roll back.

## Feedback wiring

`Orchestrator` reads the active style guide at every run and injects it
into the tailor prompt under "STYLE GUIDE" — always subordinate to the
ABSOLUTE RULES (no fabrication). Winning patterns change *phrasing*,
never facts.

## Demo with synthetic data

```bash
python scripts/seed_demo_data.py --wipe   # 48 apps, B encoded to win
hermes learn --verbose                    # see the verdict: B WINS, p<0.01
hermes learn --apply                      # promote it
hermes run --offline                      # new apps now use the guide
```

## Weekly cadence

```
scripts/learn_weekly.sh
  ├── hermes triage-email --apply
  └── hermes learn --apply
```
