import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, Bot, Brain, FileSearch, FileText, Layers, LineChart, Mail, Shield, Zap } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const FEATURES = [
  {
    icon: <Bot className="w-5 h-5" />,
    title: "7-Agent Pipeline",
    desc: "A chain of specialized agents — Scout, Analyzer, Scorer, Selector, Tailor, Cover Letter, Tracker — work together to find jobs, tailor your resume, and track every outcome.",
    tag: "Core",
  },
  {
    icon: <Layers className="w-5 h-5" />,
    title: "Master CV Database",
    desc: "One complete, structured record of your career. Every tailored resume is selected from this database — experiences, projects, skills, education — never invented.",
    tag: "Core",
  },
  {
    icon: <FileSearch className="w-5 h-5" />,
    title: "Job Scout",
    desc: "Scrapes 8+ job boards (LinkedIn, Indeed, Glassdoor) plus Greenhouse/Lever public APIs. Fuzzy deduplication means the same role on three boards is one application.",
    tag: "Discovery",
  },
  {
    icon: <Brain className="w-5 h-5" />,
    title: "Smart Tailoring",
    desc: "The agent ranks your experience against each job (0.7 keyword + 0.3 semantic similarity), picks the top 3 experiences and 3 projects, then composes an ATS-friendly resume.",
    tag: "Core",
  },
  {
    icon: <Shield className="w-5 h-5" />,
    title: "Fabrication Guardrails",
    desc: "Every tailored fact traces back to your Master CV. Invented companies, dates, or gap-skills are flagged and surfaced in the UI before you ever see them.",
    tag: "Safety",
  },
  {
    icon: <FileText className="w-5 h-5" />,
    title: "LaTeX PDF Export",
    desc: "Professional-quality PDFs via pdflatex using the Trey Hunner resume template. Cover letters in a matching template. Editable .tex source included.",
    tag: "Output",
  },
  {
    icon: <LineChart className="w-5 h-5" />,
    title: "Learning Loop",
    desc: "Every application is randomly assigned variant A or B. Once 30+ outcomes accumulate, a chi-squared test declares the winner and its phrasing patterns roll into the next tailor.",
    tag: "Learning",
  },
  {
    icon: <Mail className="w-5 h-5" />,
    title: "Email Triage",
    desc: "Connect IMAP to auto-classify offer, interview, and rejection emails. Fuzzy company matching feeds outcomes back into the tracker without manual data entry.",
    tag: "Learning",
  },
  {
    icon: <Zap className="w-5 h-5" />,
    title: "Stealth Auto-Fill",
    desc: "A hardened Playwright browser fills application forms using your real resume data — but never auto-submits. You click the final button, every time.",
    tag: "Automation",
  },
];

const TAG_COLORS: Record<string, string> = {
  Core: "bg-primary/20 text-primary",
  Discovery: "bg-blue-500/20 text-blue-300",
  Safety: "bg-amber-500/20 text-amber-300",
  Output: "bg-purple-500/20 text-purple-300",
  Learning: "bg-emerald-500/20 text-emerald-300",
  Automation: "bg-rose-500/20 text-rose-300",
};

export function FeaturesPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      {/* header */}
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Features</h1>
        </header>
      </div>

      {/* hero */}
      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Everything the agent does,", className: "font-normal" },
                { text: "in one place.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            From job discovery to tailored PDFs, every step is grounded in your
            real experience. The agent never fabricates, never auto-submits, and
            gets sharper with every application.
          </p>
        </div>
      </section>

      {/* feature grid */}
      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              className="bg-[#101010] border border-primary/10 rounded-2xl p-6 flex flex-col gap-4"
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                  {f.icon}
                </div>
                <span className={`text-[10px] px-2.5 py-1 rounded-full ${TAG_COLORS[f.tag] || "bg-primary/10 text-primary"}`}>
                  {f.tag}
                </span>
              </div>
              <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>{f.title}</h3>
              <p className="text-primary/60 text-sm leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-6xl mx-auto text-center">
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
