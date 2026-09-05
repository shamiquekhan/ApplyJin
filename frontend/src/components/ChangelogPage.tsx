import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, CheckCircle, Clock, Rocket, Star } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const VERSIONS = [
  {
    version: "Phase 8",
    date: "Sep 2026",
    tag: "Latest",
    tagColor: "bg-emerald-500/20 text-emerald-300",
    changes: [
      "Chrome extension (Manifest V3) — auto-fill, JD extraction, ghost scoring",
      "Extension icons and 3-tab popup UI (Autofill / Extract JD / Settings)",
      "Content script for form detection across 6+ job board patterns",
    ],
  },
  {
    version: "Phase 7",
    date: "Sep 2026",
    changes: [
      "Visa sponsorship lookup (DOL OFLC data, 200+ known sponsors)",
      "Salary insights (BLS OES medians, Adzuna API, location multipliers)",
      "Research tab in Console with combined visa + salary lookup",
    ],
  },
  {
    version: "Phase 6",
    date: "Sep 2026",
    changes: [
      "Kanban pipeline board (7 columns: Saved → Ghosted)",
      "LinkedIn headline + About generator from Master CV",
      "RAG-grounded chat copilot (Master CV + ChromaDB + JD context)",
      "Pipeline tab and LinkedIn tab in Console",
    ],
  },
  {
    version: "Phase 5",
    date: "Sep 2026",
    changes: [
      "Fit-score decomposition (keyword/semantic/seniority/experience bars)",
      "Ghost-job scoring (0–100 genuineness heuristic on every JD)",
      "Per-category keyword breakdown (hard skills, tools, soft skills, certs)",
      "Keyword chips (matched green / missing red) in Applications table",
    ],
  },
  {
    version: "Phase 4",
    date: "Aug 2026",
    changes: [
      "ApplyJin frontend — landing page + 9-tab Console",
      "LaTeX PDF export with Trey Hunner resume template",
      "Docker deployment (Render backend + Vercel frontend)",
      "Google OAuth sign-in for the Console",
      "Settings panel — add API keys from the UI",
    ],
  },
  {
    version: "Phase 3",
    date: "Aug 2026",
    changes: [
      "Learning loop — A/B testing with chi-squared statistics",
      "Email triage — IMAP auto-classification of outcomes",
      "Style guide promotion and rollback",
      "Keyword lift analysis and ATS-delta correlation",
    ],
  },
  {
    version: "Phase 2",
    date: "Jul 2026",
    changes: [
      "ChromaDB RAG experience retrieval",
      "Stealth Playwright auto-fill (never auto-submits)",
      "PDF generation (LaTeX + Playwright fallback)",
      "Cover letter and email template generation",
    ],
  },
  {
    version: "Phase 1",
    date: "Jul 2026",
    changes: [
      "Pipeline foundation — scout, analyze, score, tailor, track",
      "SQLite tracker with A/B variant assignment",
      "Job Scout (JobSpy + Greenhouse/Lever APIs)",
      "Fabrication guardrails and human review flow",
    ],
  },
];

export function ChangelogPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Changelog</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "What's new,", className: "font-normal" },
                { text: "every step.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            Eight phases, from pipeline foundation to Chrome extension.
            Each phase built on the last.
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-3xl mx-auto space-y-6">
          {VERSIONS.map((v, i) => (
            <motion.div
              key={v.version}
              className="bg-[#101010] border border-primary/10 rounded-2xl p-6"
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-center gap-3 mb-4">
                <h3 className="text-base font-medium" style={{ color: "#E1E0CC" }}>{v.version}</h3>
                <span className="text-xs text-primary/40">{v.date}</span>
                {v.tag && (
                  <span className={`text-[10px] px-2.5 py-0.5 rounded-full ${v.tagColor}`}>
                    {v.tag}
                  </span>
                )}
              </div>
              <ul className="space-y-2">
                {v.changes.map((change, ci) => (
                  <li key={ci} className="flex items-start gap-2 text-sm text-primary/60">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-500/50 mt-0.5 shrink-0" />
                    {change}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-3xl mx-auto text-center">
          <a
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-primary text-black rounded-full px-6 py-3 text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Open the Console
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>
    </div>
  );
}
