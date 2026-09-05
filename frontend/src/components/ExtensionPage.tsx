import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, Globe, Lock, Settings, Wand2 } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const TABS = [
  {
    icon: <Wand2 className="w-5 h-5" />,
    title: "Autofill",
    desc: "Scans the current page for form fields (name, email, phone, LinkedIn, etc.), shows detected fields with status badges, and fills them all with one click.",
  },
  {
    icon: <Globe className="w-5 h-5" />,
    title: "Extract JD",
    desc: "Automatically extracts job title, company, and full description from LinkedIn, Greenhouse, Lever, Workday, and generic job boards. Scores the JD via the backend.",
  },
  {
    icon: <Settings className="w-5 h-5" />,
    title: "Settings",
    desc: "Configure your ApplyJin backend URL and auth token. Connection status shown in the header (green dot = connected).",
  },
];

const BOARDS = ["LinkedIn", "Greenhouse", "Lever", "Workday", "iCIMS", "Generic forms"];

export function ExtensionPage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Chrome Extension</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Fill forms", className: "font-normal" },
                { text: "with one click.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            A Manifest V3 extension that auto-fills job application forms
            with your tailored resume data. Never auto-submits.
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">Install</h2>
          <div className="bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8">
            <div className="space-y-4">
              {[
                "Open chrome://extensions/ in your browser",
                "Enable Developer mode (top right toggle)",
                'Click "Load unpacked"',
                "Select the extension/ directory from this repo",
                "Pin the extension to your toolbar",
              ].map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="text-xs font-mono text-primary/40 mt-0.5">{i + 1}.</span>
                  <span className="text-sm text-primary/70">{step}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">Three tabs</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {TABS.map((tab, i) => (
              <motion.div
                key={tab.title}
                className="bg-[#101010] border border-primary/10 rounded-2xl p-6"
                initial={reduce ? undefined : { y: 24, opacity: 0 }}
                whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary mb-4">
                  {tab.icon}
                </div>
                <h3 className="text-base font-medium mb-2" style={{ color: "#E1E0CC" }}>{tab.title}</h3>
                <p className="text-primary/60 text-sm leading-relaxed">{tab.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-6">Supported job boards</h2>
          <div className="flex flex-wrap gap-2">
            {BOARDS.map((board) => (
              <span key={board} className="text-xs bg-primary/10 text-primary/70 px-3 py-1.5 rounded-full">
                {board}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8">
          <h3 className="text-base font-medium mb-4" style={{ color: "#E1E0CC" }}>How autofill works</h3>
          <div className="space-y-3 text-sm text-primary/60">
            <p>1. The extension scans the page for <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">input</code>, <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">textarea</code>, and <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">select</code> elements.</p>
            <p>2. It detects field types using labels, placeholders, aria attributes, and name/id patterns.</p>
            <p>3. Fields are matched to your resume data (name, email, phone, LinkedIn, etc.).</p>
            <p>4. Values are set using native input setters — compatible with React, Angular, and Vue forms.</p>
            <p>5. Events are dispatched (input, change, blur) to trigger framework change detection.</p>
            <p className="text-amber-400/70">6. The submit button is never clicked. You review and submit manually.</p>
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
