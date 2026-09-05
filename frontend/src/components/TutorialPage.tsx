import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, CheckCircle, Terminal } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const STEPS = [
  { num: "01", title: "Clone & install", code: "git clone https://github.com/shamiquekhan/ApplyJin.git && cd ApplyJin\npython3 -m venv .venv && source .venv/bin/activate\npip install -e \".[all,dev]\"" },
  { num: "02", title: "Add API key", code: "echo 'GEMINI_API_KEY=your-key' > .env\n# Or skip — heuristic mode works without it" },
  { num: "03", title: "Install browser", code: "python -m playwright install chromium" },
  { num: "04", title: "Import your resume", code: "hermes index-resume path/to/resume.pdf" },
  { num: "05", title: "Start backend", code: "hermes serve  # → http://localhost:8000" },
  { num: "06", title: "Start frontend", code: "cd frontend && npm install && npm run dev\n# → http://localhost:3000" },
  { num: "07", title: "Open the Console", code: "Visit http://localhost:3000/dashboard\n→ Master CV tab: add your career data\n→ Resumes tab: upload existing resumes\n→ JDs tab: paste job descriptions\n→ Tailor & score: generate tailored resumes\n→ Pipeline: track your applications" },
];

export function TutorialPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Tutorial</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Zero to tailored", className: "font-normal" },
                { text: "in seven steps.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            Follow these steps to get ApplyJin running on your machine.
            The full pipeline works without an API key (heuristic mode).
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-3xl mx-auto space-y-6">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.num}
              className="bg-[#101010] border border-primary/10 rounded-2xl p-6"
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-mono text-primary/40">{step.num}</span>
                <h3 className="text-base font-medium" style={{ color: "#E1E0CC" }}>{step.title}</h3>
              </div>
              <pre className="bg-black/50 rounded-xl p-4 text-xs text-primary/60 overflow-x-auto whitespace-pre-wrap">
                {step.code}
              </pre>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-3xl mx-auto bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8">
          <h3 className="text-base font-medium mb-4" style={{ color: "#E1E0CC" }}>Quick reference</h3>
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-primary/50 shrink-0" />
              <span className="text-primary/60"><code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">hermes run</code> — Full pipeline: scout → analyze → score → tailor → track</span>
            </div>
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-primary/50 shrink-0" />
              <span className="text-primary/60"><code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">hermes scout --ats stripe</code> — Search specific ATS boards</span>
            </div>
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-primary/50 shrink-0" />
              <span className="text-primary/60"><code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">hermes review</code> — Approve or reject applications</span>
            </div>
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-primary/50 shrink-0" />
              <span className="text-primary/60"><code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">hermes fill --id 1</code> — Auto-fill a form (never auto-submits)</span>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle className="w-4 h-4 text-emerald-500/50 shrink-0" />
              <span className="text-primary/60">Tests: <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">python -m pytest tests/ -q</code> (164 passing)</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
