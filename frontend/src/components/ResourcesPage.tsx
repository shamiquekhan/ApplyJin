import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, BookOpen, Code, ExternalLink, FileText, Globe, Mail, Newspaper, Rocket, Shield, Terminal } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const RESOURCES = [
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: "Tutorial",
    desc: "Complete step-by-step guide to running ApplyJin locally, from zero to tailored resumes.",
    link: "/tutorial",
    tag: "Start here",
  },
  {
    icon: <Shield className="w-5 h-5" />,
    title: "Guardrails",
    desc: "Non-negotiable safety rules: no fabrication, no auto-submit, rate limiting, privacy-first design.",
    link: "/guardrails",
    tag: "Safety",
  },
  {
    icon: <Terminal className="w-5 h-5" />,
    title: "API Reference",
    desc: "All 40+ REST endpoints documented: auth, Master CV, resumes, JDs, tailoring, pipeline, research.",
    link: "/api",
    tag: "Developer",
  },
  {
    icon: <ExternalLink className="w-5 h-5" />,
    title: "GitHub Repository",
    desc: "Source code, issues, and releases. Star the repo if you find it useful.",
    link: "https://github.com/shamiquekhan/ApplyJin",
    external: true,
    tag: "Code",
  },
  {
    icon: <Globe className="w-5 h-5" />,
    title: "Chrome Extension",
    desc: "Auto-fill job applications directly from your browser. Supports LinkedIn, Greenhouse, Lever, and more.",
    link: "/extension",
    tag: "Tool",
  },
  {
    icon: <FileText className="w-5 h-5" />,
    title: "Features",
    desc: "Full feature list: 16 capabilities across job scouting, tailoring, pipeline, research, and automation.",
    link: "/features",
    tag: "Overview",
  },
  {
    icon: <Code className="w-5 h-5" />,
    title: "Architecture",
    desc: "How the system is built: FastAPI backend, React frontend, ChromaDB vectors, SQLite storage.",
    link: "/architecture",
    tag: "Deep dive",
  },
  {
    icon: <Newspaper className="w-5 h-5" />,
    title: "Changelog",
    desc: "What's new in each version. Phases 1–8 complete: pipeline, learning, dashboards, research, extension.",
    link: "/changelog",
    tag: "Updates",
  },
];

export function ResourcesPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Resources</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Everything you need,", className: "font-normal" },
                { text: "in one place.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            Documentation, guides, API references, and tools to get the most
            out of ApplyJin.
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {RESOURCES.map((r, i) => (
            <motion.a
              key={r.title}
              href={r.link}
              {...(r.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              className="bg-[#101010] border border-primary/10 rounded-2xl p-6 flex flex-col gap-4 hover:border-primary/30 transition-colors group"
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                  {r.icon}
                </div>
                <span className="text-[10px] px-2.5 py-1 rounded-full bg-primary/10 text-primary">
                  {r.tag}
                </span>
              </div>
              <h3 className="text-base font-medium" style={{ color: "#E1E0CC" }}>{r.title}</h3>
              <p className="text-primary/60 text-sm leading-relaxed flex-1">{r.desc}</p>
              <div className="flex items-center gap-1 text-xs text-primary/40 group-hover:text-primary/70 transition-colors">
                {r.external ? "Open" : "Read more"} <ArrowRight className="w-3 h-3" />
              </div>
            </motion.a>
          ))}
        </div>
      </section>
    </div>
  );
}
