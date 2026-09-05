import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, Box, Database, Globe, Layers, Server, Shield } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const LAYERS = [
  {
    icon: <Globe className="w-5 h-5" />,
    name: "Frontend",
    tech: "React 18 + Vite + TypeScript + Tailwind",
    desc: "Landing page, 9-tab Console, Kanban board, copilot chat, research panel.",
    color: "text-blue-400",
  },
  {
    icon: <Server className="w-5 h-5" />,
    name: "Backend",
    tech: "Python 3.11 + FastAPI + Uvicorn",
    desc: "40+ REST endpoints: auth, Master CV, tailoring, pipeline, research, copilot.",
    color: "text-emerald-400",
  },
  {
    icon: <Layers className="w-5 h-5" />,
    name: "LLM Layer",
    tech: "Gemini 3.6 Flash + Groq + Ollama",
    desc: "Model-pool rotation under free-tier 20 RPM limits. Heuristic fallback when keyless.",
    color: "text-purple-400",
  },
  {
    icon: <Database className="w-5 h-5" />,
    name: "Storage",
    tech: "SQLite + ChromaDB + File artifacts",
    desc: "Single SQLite file for tracker + master CV. ChromaDB for RAG experience vectors.",
    color: "text-amber-400",
  },
  {
    icon: <Shield className="w-5 h-5" />,
    name: "Guardrails",
    tech: "No fabrication + No auto-submit + Rate limits",
    desc: "Every tailored fact traces to Master CV. Browser fills forms but never submits.",
    color: "text-rose-400",
  },
  {
    icon: <Box className="w-5 h-5" />,
    name: "Extension",
    tech: "Chrome Manifest V3",
    desc: "Content script for form detection + autofill. Service worker for storage.",
    color: "text-cyan-400",
  },
];

const PIPELINE = [
  "Job Scout",
  "JD Analyzer",
  "Fit Scorer",
  "Ghost Scorer",
  "Selector",
  "Tailor v3",
  "Cover Letter",
  "Export (LaTeX/PDF)",
  "Tracker",
  "Learning Loop",
];

export function ArchitecturePage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Architecture</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "How the system", className: "font-normal" },
                { text: "is built.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            A split-deployment architecture: React frontend on Vercel,
            Python backend on Render, Chrome extension for browser automation.
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">System layers</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {LAYERS.map((layer, i) => (
              <motion.div
                key={layer.name}
                className="bg-[#101010] border border-primary/10 rounded-2xl p-6"
                initial={reduce ? undefined : { y: 24, opacity: 0 }}
                whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className={`w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center ${layer.color} mb-4`}>
                  {layer.icon}
                </div>
                <h3 className="text-base font-medium mb-1" style={{ color: "#E1E0CC" }}>{layer.name}</h3>
                <p className="text-primary/40 text-xs font-mono mb-2">{layer.tech}</p>
                <p className="text-primary/60 text-sm leading-relaxed">{layer.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">Pipeline flow</h2>
          <div className="bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8">
            <div className="flex flex-wrap items-center gap-2">
              {PIPELINE.map((step, i) => (
                <div key={step} className="flex items-center gap-2">
                  <span className="text-xs bg-primary/10 text-primary/70 px-3 py-1.5 rounded-full whitespace-nowrap">
                    {step}
                  </span>
                  {i < PIPELINE.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-primary/30" />
                  )}
                </div>
              ))}
            </div>
            <p className="text-primary/40 text-xs mt-4">
              Each step feeds into the next. Guardrails validate at the Tailor stage.
              The Learning Loop feeds style patterns back into the next Tailor run.
            </p>
          </div>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">Deployment</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#101010] border border-primary/10 rounded-2xl p-6">
              <h3 className="text-base font-medium mb-2" style={{ color: "#E1E0CC" }}>Backend → Render</h3>
              <p className="text-primary/60 text-sm leading-relaxed">
                Docker multi-stage build. Includes texlive for LaTeX PDFs.
                SQLite is ephemeral on Render (resets on deploy). For persistent
                data, run locally.
              </p>
            </div>
            <div className="bg-[#101010] border border-primary/10 rounded-2xl p-6">
              <h3 className="text-base font-medium mb-2" style={{ color: "#E1E0CC" }}>Frontend → Vercel</h3>
              <p className="text-primary/60 text-sm leading-relaxed">
                Vite SPA with VITE_API_URL pointing to the Render backend.
                All *.vercel.app origins are CORS-allowed.
              </p>
            </div>
          </div>
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
