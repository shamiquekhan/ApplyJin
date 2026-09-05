import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, Ban, CheckCircle, Eye, Lock, Shield, UserCheck } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const GUARDRAILS = [
  {
    icon: <Ban className="w-5 h-5" />,
    title: "No fabrication",
    desc: "Every tailored fact traces back to your Master CV database. Invented companies, dates, or gap-skills are flagged and surfaced in the UI before you ever see them.",
    detail: "The tailor agent receives only selected facts from your Master CV. A post-hoc guardrail pass compares every claim in the output against the database. Violations are highlighted in red in the Console — you decide whether to fix or discard.",
  },
  {
    icon: <UserCheck className="w-5 h-5" />,
    title: "No auto-submit",
    desc: "The browser agent fills application forms and stops. The human clicks submit, every time.",
    detail: "Playwright fills fields using native input setters (compatible with React/Angular forms) but never triggers the submit button. The extension and the CLI fill commands both enforce this. You review every application before it goes out.",
  },
  {
    icon: <Lock className="w-5 h-5" />,
    title: "Rate limiting",
    desc: "Maximum applications per day (default 20), enforced in the tracker. Prevents spam and keeps your signal clean.",
    detail: "The tracker counts daily submissions and blocks new tailoring once the limit is hit. You can adjust the limit in settings. This protects your accounts from flagged behavior and keeps your application quality high.",
  },
  {
    icon: <Eye className="w-5 h-5" />,
    title: "No duplicates",
    desc: "The same job is never applied to twice. Fuzzy deduplication catches the same role posted on multiple boards.",
    detail: "Before creating a new application, the system checks for existing entries with the same company + title combination (fuzzy-matched). If a match is found, it surfaces the existing record instead of creating a duplicate.",
  },
  {
    icon: <Shield className="w-5 h-5" />,
    title: "Privacy-first",
    desc: "Everything runs locally: SQLite, ChromaDB, files. Your .env and configs are gitignored. No telemetry, no tracking.",
    detail: "Your resume data, Master CV, application history, and API keys never leave your machine (unless you deploy to Render/Vercel). The Chrome extension only communicates with your own backend. No third-party analytics or tracking scripts.",
  },
  {
    icon: <CheckCircle className="w-5 h-5" />,
    title: "Human review",
    desc: "Every application requires your approval before submission. The agent drafts, you decide.",
    detail: "The Console shows every tailored resume, cover letter, and email before it goes out. You can edit, reject, or approve each one. The pipeline status only advances when you take action. Nothing moves without your say-so.",
  },
];

export function GuardrailsPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Guardrails</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Safety by design,", className: "font-normal" },
                { text: "not by accident.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            ApplyJin is built with non-negotiable guardrails. The agent automates
            the pipeline — but never crosses the line into spam, fabrication, or
            autonomous submission.
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto space-y-6">
          {GUARDRAILS.map((g, i) => (
            <motion.div
              key={g.title}
              className="bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8"
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
                  {g.icon}
                </div>
                <div>
                  <h3 className="text-lg font-medium mb-2" style={{ color: "#E1E0CC" }}>{g.title}</h3>
                  <p className="text-primary/60 text-sm leading-relaxed mb-3">{g.desc}</p>
                  <p className="text-primary/40 text-xs leading-relaxed">{g.detail}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto text-center">
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
