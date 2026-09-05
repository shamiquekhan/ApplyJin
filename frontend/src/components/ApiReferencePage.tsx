import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { navigate } from "../lib/router";

const SECTIONS = [
  {
    title: "Health & Auth",
    endpoints: [
      { method: "GET", path: "/api/auth/google", desc: "Initiate Google OAuth flow" },
      { method: "GET", path: "/api/auth/google/callback", desc: "Google OAuth callback — mints JWT" },
      { method: "GET", path: "/api/auth/me", desc: "Current user profile (requires JWT)" },
      { method: "POST", path: "/api/auth/logout", desc: "Invalidate current session" },
    ],
  },
  {
    title: "Master CV",
    endpoints: [
      { method: "GET", path: "/api/master/profile", desc: "Get profile (name, email, headline, etc.)" },
      { method: "PUT", path: "/api/master/profile", desc: "Update profile" },
      { method: "GET", path: "/api/master/stats", desc: "Entry counts (experiences, projects, skills, etc.)" },
      { method: "GET", path: "/api/master/experiences", desc: "List all experiences" },
      { method: "POST", path: "/api/master/experiences", desc: "Add an experience entry" },
      { method: "DELETE", path: "/api/master/experiences/{entry_id}", desc: "Delete an experience" },
      { method: "GET", path: "/api/master/projects", desc: "List all projects" },
      { method: "POST", path: "/api/master/projects", desc: "Add a project entry" },
      { method: "DELETE", path: "/api/master/projects/{entry_id}", desc: "Delete a project" },
      { method: "GET", path: "/api/master/skills", desc: "List all skills by category" },
      { method: "POST", path: "/api/master/skills", desc: "Add skills to a category" },
      { method: "POST", path: "/api/master/import-resume", desc: "Import PDF/DOCX/MD into Master CV" },
    ],
  },
  {
    title: "Resumes",
    endpoints: [
      { method: "GET", path: "/api/resumes", desc: "List all uploaded resumes" },
      { method: "GET", path: "/api/resumes/{resume_id}", desc: "Get resume details + structured data" },
      { method: "POST", path: "/api/resumes/upload", desc: "Upload a resume (PDF/DOCX/MD)" },
      { method: "POST", path: "/api/resumes/create", desc: "Create a resume from structured data" },
      { method: "DELETE", path: "/api/resumes/{resume_id}", desc: "Delete a resume" },
    ],
  },
  {
    title: "Job Descriptions",
    endpoints: [
      { method: "GET", path: "/api/job-descriptions", desc: "List all JDs (includes ghost scores)" },
      { method: "GET", path: "/api/job-descriptions/{jd_id}", desc: "Get JD details" },
      { method: "POST", path: "/api/job-descriptions", desc: "Add a JD (title, company, description, url)" },
      { method: "GET", path: "/api/job-descriptions/{jd_id}/contacts", desc: "Extract contacts from JD" },
      { method: "POST", path: "/api/job-descriptions/{jd_id}/extract-keywords", desc: "Extract keywords from JD" },
    ],
  },
  {
    title: "Tailoring & Scoring",
    endpoints: [
      { method: "POST", path: "/api/score", desc: "Score a resume against a JD (fit breakdown)" },
      { method: "POST", path: "/api/applications/{app_id}/tailor", desc: "Tailor resume for a specific application" },
      { method: "POST", path: "/api/applications/{app_id}/cover-letter", desc: "Generate cover letter" },
      { method: "POST", path: "/api/applications/{app_id}/email-template", desc: "Generate email template" },
    ],
  },
  {
    title: "Applications & Downloads",
    endpoints: [
      { method: "GET", path: "/api/applications", desc: "List all applications (with fit breakdowns)" },
      { method: "GET", path: "/api/applications/{app_id}", desc: "Get application details" },
      { method: "GET", path: "/api/applications/{app_id}/download-resume", desc: "Download tailored resume (Markdown)" },
      { method: "GET", path: "/api/applications/{app_id}/download-resume-latex", desc: "Download tailored resume (LaTeX + PDF)" },
      { method: "GET", path: "/api/applications/{app_id}/download-cover-letter", desc: "Download cover letter" },
    ],
  },
  {
    title: "Pipeline (Kanban)",
    endpoints: [
      { method: "GET", path: "/api/pipeline", desc: "Applications grouped by pipeline status" },
      { method: "POST", path: "/api/pipeline/{app_id}/status", desc: "Move application to new status" },
    ],
  },
  {
    title: "Copilot (RAG Chat)",
    endpoints: [
      { method: "POST", path: "/api/copilot/chat", desc: "Chat about a tailored match (RAG-grounded)" },
      { method: "GET", path: "/api/copilot/history/{app_id}", desc: "Chat history for an application" },
    ],
  },
  {
    title: "LinkedIn & Research",
    endpoints: [
      { method: "POST", path: "/api/linkedin/generate", desc: "Generate LinkedIn headline + About from Master CV" },
      { method: "GET", path: "/api/visa-sponsorship/{company}", desc: "Visa sponsorship lookup for a company" },
      { method: "POST", path: "/api/visa-sponsorship", desc: "Manually mark an employer as sponsor/non-sponsor" },
      { method: "GET", path: "/api/salary-insights", desc: "Salary insights (title, location, company)" },
    ],
  },
  {
    title: "Settings & Public",
    endpoints: [
      { method: "GET", path: "/api/settings/llm", desc: "Get LLM config (keys redacted)" },
      { method: "POST", path: "/api/settings/llm", desc: "Update LLM config (Gemini/Groq/Ollama keys)" },
      { method: "GET", path: "/api/public/stats", desc: "Public stats (applications, interviews, etc.)" },
    ],
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-500/20 text-emerald-300",
  POST: "bg-blue-500/20 text-blue-300",
  PUT: "bg-amber-500/20 text-amber-300",
  DELETE: "bg-red-500/20 text-red-300",
};

export function ApiReferencePage() {
  const reduce = useReducedMotion();

  return (
    <div className="min-h-screen bg-black">
      <div className="p-4 md:p-6">
        <header className="flex items-center gap-3 mb-12">
          <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5">
            <ArrowLeft className="w-4 h-4" /> ApplyJin
          </button>
          <span className="text-primary/30">/</span>
          <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>API Reference</h1>
        </header>
      </div>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
            <WordsPullUpMultiStyle
              segments={[
                { text: "40+ endpoints,", className: "font-normal" },
                { text: "fully documented.", className: "italic font-serif" },
              ]}
            />
          </h2>
          <p className="text-primary/70 text-sm md:text-base max-w-xl mx-auto mt-6">
            The ApplyJin backend exposes a REST API for everything: Master CV
            management, resume tailoring, pipeline tracking, research, and
            the RAG copilot.
          </p>
          <p className="text-primary/50 text-xs mt-4">
            Base URL: <code className="bg-primary/10 px-2 py-0.5 rounded">http://localhost:8000</code> (local) or your Render URL
          </p>
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto space-y-8">
          {SECTIONS.map((section, si) => (
            <motion.div
              key={section.title}
              initial={reduce ? undefined : { y: 24, opacity: 0 }}
              whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: si * 0.05, ease: [0.16, 1, 0.3, 1] }}
            >
              <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-4">{section.title}</h2>
              <div className="bg-[#101010] border border-primary/10 rounded-2xl overflow-hidden">
                {section.endpoints.map((ep, ei) => (
                  <div
                    key={ep.path + ep.method}
                    className={`flex items-center gap-3 px-5 py-3 text-sm ${ei < section.endpoints.length - 1 ? "border-b border-primary/5" : ""}`}
                  >
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded shrink-0 ${METHOD_COLORS[ep.method] || "bg-primary/10 text-primary"}`}>
                      {ep.method}
                    </span>
                    <code className="text-primary/70 font-mono text-xs shrink-0 min-w-[200px]">{ep.path}</code>
                    <span className="text-primary/40 text-xs hidden sm:inline">{ep.desc}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-4 md:px-6 pb-16 md:pb-24">
        <div className="max-w-4xl mx-auto bg-[#101010] border border-primary/10 rounded-2xl p-6 md:p-8">
          <h3 className="text-base font-medium mb-4" style={{ color: "#E1E0CC" }}>Authentication</h3>
          <p className="text-primary/60 text-sm leading-relaxed mb-4">
            Most endpoints require a JWT token in the <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs">Authorization: Bearer &lt;token&gt;</code> header.
            The token is minted after Google OAuth login and stored in the browser's localStorage.
          </p>
          <p className="text-primary/60 text-sm leading-relaxed mb-4">
            When running locally without Google OAuth configured, the API is open — no token needed.
          </p>
          <h4 className="text-sm font-medium mb-2" style={{ color: "#E1E0CC" }}>Example request</h4>
          <pre className="bg-black/50 rounded-xl p-4 text-xs text-primary/60 overflow-x-auto">
{`curl -X POST http://localhost:8000/api/score \\
  -H "Content-Type: application/json" \\
  -d '{"resume_id": 1, "jd_id": 1}'`}
          </pre>
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
