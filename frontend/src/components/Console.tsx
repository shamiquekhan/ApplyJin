import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Bot, Check, Database, Download, FileText, Loader2, Link, Mail, Settings, Shield, Sparkles, Trash2 } from "lucide-react";
import * as api from "../lib/api";
import { markdownToHtml } from "../lib/markdown";
import type { ApplicationRow, KeywordBuckets, ResumeSummary, JDSummary, Scores, TailorResult, MasterStats, MasterExperience, MasterProject } from "../lib/api";
import { navigate } from "../lib/router";
import { fetchMe, logout } from "../lib/session";
import { CopilotChat } from "./CopilotChat";
import { KanbanBoard } from "./KanbanBoard";

/* ---------- shared atoms (ApplyJin design system) ---------- */

const cardCls = "bg-[#101010] rounded-2xl border border-primary/10";
const inputCls =
  "w-full bg-black/40 border border-primary/20 rounded-xl px-4 py-2.5 text-sm text-[#E1E0CC] placeholder:text-primary/30 outline-none focus:border-primary/50 transition-colors";

function GhostBadge({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  const color = score >= 80 ? "text-emerald-400" : score >= 50 ? "text-amber-400" : "text-red-400";
  const label = score >= 80 ? "Likely genuine" : score >= 50 ? "Possibly stale" : "Likely stale";
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${color} border-current/20`} title={label}>
      <Shield className="w-2.5 h-2.5 inline -mt-0.5 mr-0.5" />{score}
    </span>
  );
}

function Toast({ note }: { note: { text: string; error?: boolean } | null }) {
  return (
    <div aria-live="polite" role="status">
      <AnimatePresence>
        {note && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-medium ${
              note.error ? "bg-red-500 text-white" : "bg-primary text-black"
            }`}
          >
            {note.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Bar({ value, tone }: { value: number; tone: string }) {
  return (
    <div className="h-1.5 bg-primary/10 rounded-full overflow-hidden">
      <div className={`h-full ${tone} rounded-full transition-all duration-700`} style={{ width: `${Math.min(value, 100)}%` }} />
    </div>
  );
}

/* ---------- panel: Resumes ---------- */

function ResumesPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try { setResumes(await api.listResumes()); } catch { /* backend down */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function onUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return toast("Choose a file first", true);
    setBusy(true);
    try {
      const res = await api.uploadResume(file, name);
      toast(`Parsed ${res.bullets} bullets from ${file.name}`);
      setName(""); setContent("");
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (e) { toast(e instanceof Error ? e.message : "Upload failed", true); }
    finally { setBusy(false); }
  }

  async function onPaste() {
    if (!content.trim()) return toast("Paste your resume text first", true);
    setBusy(true);
    try { await api.createResume(name || "Pasted resume", content); toast("Resume saved"); setName(""); setContent(""); refresh(); }
    catch (e) { toast(e instanceof Error ? e.message : "Save failed", true); }
    finally { setBusy(false); }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-4">
      <div className={`${cardCls} p-6 lg:col-span-2 space-y-5 h-fit`}>
        <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Add a resume</h3>
        <div className="space-y-3">
          <input className={inputCls} placeholder="Name — e.g. AI Engineer v1" value={name} onChange={(e) => setName(e.target.value)} />
          <div>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.md,.txt"
              className="w-full text-xs text-primary/60 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary/10 file:text-primary text-sm" />
            <button onClick={onUpload} disabled={busy}
              className="mt-2 w-full bg-primary text-black rounded-full py-2.5 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} Upload &amp; parse
            </button>
          </div>
          <div className="pt-3 border-t border-primary/10 space-y-3">
            <textarea className={`${inputCls} resize-none`} rows={5} placeholder="…or paste resume text / markdown"
              value={content} onChange={(e) => setContent(e.target.value)} />
            <button onClick={onPaste} disabled={busy}
              className="w-full border border-primary/30 text-primary rounded-full py-2.5 text-sm hover:bg-primary/10 transition-colors disabled:opacity-50">
              Save from text
            </button>
          </div>
        </div>
      </div>

      <div className={`${cardCls} p-6 lg:col-span-3`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Your resumes</h3>
          <button onClick={refresh} className="text-xs text-primary/60 hover:text-primary">Refresh</button>
        </div>
        <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
          {resumes.length === 0 && <p className="text-primary/40 text-sm">Nothing here yet — add your first resume.</p>}
          {resumes.map((r) => (
            <div key={r.id} className="border border-primary/10 rounded-xl p-4 hover:border-primary/30 transition-colors">
              <p className="font-medium text-sm" style={{ color: "#E1E0CC" }}>{r.name}</p>
              <p className="text-primary/40 text-xs mt-1 line-clamp-2">{r.preview}</p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {r.skills.slice(0, 8).map((s) => (
                  <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary/80">{s}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- panel: Job descriptions ---------- */

function JDsPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [jds, setJDs] = useState<JDSummary[]>([]);
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try { setJDs(await api.listJDs()); } catch { /* down */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function save() {
    if (!title.trim() || !company.trim() || content.trim().length < 30)
      return toast("Title, company and JD text (30+ chars) are needed", true);
    setBusy(true);
    try { await api.addJD(title, company, content); toast("Job description saved"); setTitle(""); setCompany(""); setContent(""); refresh(); }
    catch (e) { toast(e instanceof Error ? e.message : "Save failed", true); }
    finally { setBusy(false); }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-4">
      <div className={`${cardCls} p-6 lg:col-span-2 space-y-3 h-fit`}>
        <h3 className="text-lg font-medium mb-3" style={{ color: "#E1E0CC" }}>Add a job description</h3>
        <input className={inputCls} placeholder="Job title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input className={inputCls} placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
        <textarea className={`${inputCls} resize-none`} rows={9} placeholder="Paste the full job description…"
          value={content} onChange={(e) => setContent(e.target.value)} />
        <button onClick={save} disabled={busy}
          className="w-full bg-primary text-black rounded-full py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Save job description
        </button>
      </div>

      <div className={`${cardCls} p-6 lg:col-span-3`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Saved job descriptions</h3>
          <button onClick={refresh} className="text-xs text-primary/60 hover:text-primary">Refresh</button>
        </div>
        <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
          {jds.length === 0 && <p className="text-primary/40 text-sm">No job descriptions yet.</p>}
          {jds.map((j) => (
            <div key={j.id} className="border border-primary/10 rounded-xl p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium text-sm" style={{ color: "#E1E0CC" }}>{j.title}</p>
                  <p className="text-primary/50 text-xs mt-0.5">{j.company}</p>
                </div>
                <GhostBadge score={j.ghost_score} />
              </div>
              <p className="text-primary/40 text-xs mt-2 line-clamp-3">{j.preview}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- panel: Tailor & score ---------- */

const KEYWORD_GROUPS: { key: keyof KeywordBuckets; label: string }[] = [
  { key: "hard_skills", label: "Hard skills" },
  { key: "tools", label: "Tools" },
  { key: "soft_skills", label: "Soft skills" },
  { key: "domain_keywords", label: "Domain" },
  { key: "certifications", label: "Certifications" },
];

function TailorPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [jds, setJDs] = useState<JDSummary[]>([]);
  const [resumeId, setResumeId] = useState("");
  const [jdId, setJdId] = useState("");
  const [before, setBefore] = useState<Scores | null>(null);
  const [keywords, setKeywords] = useState<KeywordBuckets | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [appId, setAppId] = useState<number | null>(null);
  const [result, setResult] = useState<TailorResult | null>(null);
  const [cover, setCover] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [preview, setPreview] = useState<"resume" | "cover" | "email">("resume");

  useEffect(() => {
    api.listResumes().then(setResumes).catch(() => undefined);
    api.listJDs().then(setJDs).catch(() => undefined);
  }, []);

  async function analyze() {
    if (!resumeId || !jdId) return toast("Pick a resume and a job description", true);
    setBusy("analyze"); setResult(null); setCover(null); setKeywords(null); setSelected(new Set());
    try {
      const app = await api.createApplication(Number(resumeId), Number(jdId));
      setAppId(app.id);
      setBefore(app.scores_before);
      toast("Extracting keywords with the agent…");
      const kws = await api.extractKeywords(Number(jdId));
      setKeywords(kws);
      toast("Keywords ready — tick the ones you genuinely have");
    } catch (e) { toast(e instanceof Error ? e.message : "Analyze failed", true); }
    finally { setBusy(null); }
  }

  async function tailor() {
    if (!appId) return;
    if (selected.size === 0) return toast("Select at least one keyword", true);
    setBusy("tailor");
    try {
      const res = await api.tailorResumeV3(appId, [...selected]);
      setResult(res);
      setCover(""); setEmail("");
      setPreview("resume");
      toast(res.validated ? `Tailored — ATS ${res.delta.overall >= 0 ? "+" : ""}${res.delta.overall} pts` : "Tailored with guardrail warnings — review carefully");
    } catch (e) { toast(e instanceof Error ? e.message : "Tailoring failed", true); }
    finally { setBusy(null); }
  }

  async function makeCover() {
    if (!appId) return;
    setBusy("cover");
    try {
      const res = await api.generateCoverLetter(appId);
      setCover(res.cover_letter_md);
      setPreview("cover");
      toast("Cover letter written");
    } catch (e) { toast(e instanceof Error ? e.message : "Failed", true); }
    finally { setBusy(null); }
  }

  async function makeEmail(templateType: string) {
    if (!appId) return;
    setBusy("email");
    try {
      const res = await api.emailTemplate(appId, templateType);
      setEmail(res.email_md);
      setPreview("email");
      toast(res.hiring_manager ? `Email drafted — addressed to ${res.hiring_manager}` : "Email drafted");
    } catch (e) { toast(e instanceof Error ? e.message : "Failed", true); }
    finally { setBusy(null); }
  }

  const toggle = (kw: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(kw) ? next.delete(kw) : next.add(kw);
      return next;
    });

  return (
    <div className="grid lg:grid-cols-12 gap-4">
      {/* step 1 */}
      <div className={`${cardCls} p-6 lg:col-span-3 space-y-3 h-fit`}>
        <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>1 · Pair them up</h3>
        <select className={inputCls} value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
          <option value="">Choose a resume…</option>
          {resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <select className={inputCls} value={jdId} onChange={(e) => setJdId(e.target.value)}>
          <option value="">Choose a job description…</option>
          {jds.map((j) => <option key={j.id} value={j.id}>{j.title} @ {j.company}</option>)}
        </select>
        <button onClick={analyze} disabled={!!busy}
          className="w-full bg-primary text-black rounded-full py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {busy === "analyze" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Analyze &amp; extract keywords
        </button>

        {before && (
          <div className="pt-4 mt-2 border-t border-primary/10 space-y-3">
            {(["overall", "keyword_match", "semantic_similarity"] as const).map((k) => (
              <div key={k}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-primary/60 capitalize">{k.replace("_", " ")}</span>
                  <span className="text-primary font-medium">{before[k].toFixed(1)}%</span>
                </div>
                <Bar value={before[k]} tone="bg-primary/40" />
              </div>
            ))}
            {before.matched_keywords && before.matched_keywords.length > 0 && (
              <div className="pt-2">
                <p className="text-[10px] text-primary/40 mb-1">Matched</p>
                <div className="flex flex-wrap gap-1">
                  {before.matched_keywords.map((kw) => (
                    <span key={kw} className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300/80">{kw}</span>
                  ))}
                </div>
              </div>
            )}
            {before.missing_keywords && before.missing_keywords.length > 0 && (
              <div className="pt-1">
                <p className="text-[10px] text-primary/40 mb-1">Missing</p>
                <div className="flex flex-wrap gap-1">
                  {before.missing_keywords.map((kw) => (
                    <span key={kw} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300/80">{kw}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* step 2 */}
      <div className={`${cardCls} p-6 lg:col-span-3 h-fit`}>
        <h3 className="text-lg font-medium mb-4" style={{ color: "#E1E0CC" }}>2 · Choose keywords</h3>
        {!keywords ? (
          <p className="text-primary/40 text-sm py-8">Pair a resume and a job description first.</p>
        ) : (
          <>
            <p className="text-xs text-primary/50 mb-4">Tick the skills you <em className="font-serif italic">genuinely have</em> — the agent never invents the rest.</p>
            <div className="space-y-4 max-h-[380px] overflow-y-auto pr-1">
              {KEYWORD_GROUPS.map(({ key, label }) => {
                const items = keywords[key] || [];
                if (!items.length) return null;
                return (
                  <div key={key}>
                    <p className="text-[10px] text-primary/40 uppercase tracking-widest mb-2">{label}</p>
                    <div className="flex flex-wrap gap-2">
                      {items.map((kw) => (
                        <button key={kw} onClick={() => toggle(kw)}
                          className={`px-3.5 py-1.5 rounded-full text-xs transition-all ${
                            selected.has(kw) ? "bg-primary text-black font-medium" : "bg-primary/10 text-primary/70 hover:bg-primary/20"
                          }`}>
                          {selected.has(kw) && <Check className="w-3 h-3 inline mr-1 -mt-0.5" />}{kw}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <button onClick={tailor} disabled={!!busy || selected.size === 0}
              className="mt-5 w-full bg-primary text-black rounded-full py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
              {busy === "tailor" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Tailor resume ({selected.size})
            </button>
          </>
        )}
      </div>

      {/* step 3 */}
      <div className={`${cardCls} p-6 lg:col-span-3 h-fit`}>
        <h3 className="text-lg font-medium mb-4" style={{ color: "#E1E0CC" }}>3 · Review &amp; download</h3>
        {!result ? (
          <p className="text-primary/40 text-sm py-8">Tailored output lands here.</p>
        ) : (
          <>
            {/* selection report — what the agent chose from the master DB */}
            {result.selection && result.selection.length > 0 && (
              <div className="mb-4 p-3 rounded-xl bg-black/40 border border-primary/10">
                <p className="text-[10px] text-primary/40 uppercase tracking-widest mb-2">Selected from your master CV</p>
                {result.selection.map((s, i) => (
                  <p key={i} className="text-xs text-primary/70 leading-relaxed">
                    <span className={s.kind === "exp" ? "text-primary" : "text-primary/60"}>
                      {s.kind === "exp" ? "·" : "◇"}
                    </span>{" "}
                    {s.title.length > 52 ? s.title.slice(0, 52) + "…" : s.title}
                    {s.matched_keywords && s.matched_keywords.length > 0 && (
                      <span className="text-primary/40"> ({s.matched_keywords.slice(0, 3).join(", ")})</span>
                    )}
                  </p>
                ))}
                {result.gaps && result.gaps.length > 0 && (
                  <p className="text-[11px] text-amber-300/70 mt-2">
                    Gaps left out: {result.gaps.slice(0, 4).join(", ")}
                  </p>
                )}
              </div>
            )}
            {!result.validated && (
              <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300/90 text-xs">
                Guardrail warning: {result.guardrail_violations.join("; ").slice(0, 220)}
              </div>
            )}
            <div className="space-y-3 mb-5">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-primary/60">Overall ATS</span>
                  <span className="text-primary font-medium">{result.scores_after.overall.toFixed(1)}%</span>
                </div>
                <Bar value={result.scores_after.overall} tone="bg-primary" />
                <p className={`text-xs mt-1 font-medium ${result.delta.overall >= 0 ? "text-primary" : "text-amber-300/80"}`}>
                  {result.delta.overall >= 0 ? "+" : ""}{result.delta.overall} pts since tailoring
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 mb-3">
              <button onClick={makeCover} disabled={!!busy}
                className="border border-primary/30 text-primary rounded-full py-2.5 text-xs hover:bg-primary/10 disabled:opacity-50 flex items-center justify-center gap-1.5">
                {busy === "cover" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Cover letter
              </button>
              <a href={api.downloadUrl.resume(appId!)} target="_blank"
                className="bg-primary text-black rounded-full py-2.5 text-xs font-medium hover:opacity-90 flex items-center justify-center gap-1.5">
                <Download className="w-3.5 h-3.5" /> Resume PDF
              </a>
              {cover && (
                <a href={api.downloadUrl.cover(appId!)} target="_blank"
                  className="border border-primary/30 text-primary rounded-full py-2.5 text-xs hover:bg-primary/10 flex items-center justify-center gap-1.5">
                  <Download className="w-3.5 h-3.5" /> Cover PDF
                </a>
              )}
              <a href={api.downloadUrl.latex(appId!)} target="_blank"
                className="border border-primary/30 text-primary rounded-full py-2.5 text-xs hover:bg-primary/10 flex items-center justify-center gap-1.5">
                <Download className="w-3.5 h-3.5" /> LaTeX source
              </a>
            </div>
            {/* email templates (CV Forge model) */}
            <div className="flex items-center gap-2 mb-2">
              <Mail className="w-3.5 h-3.5 text-primary/60" />
              <p className="text-[10px] text-primary/40 uppercase tracking-widest">Email drafts</p>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-3">
              {(["application", "follow_up", "thank_you"] as const).map((t) => (
                <button key={t} onClick={() => makeEmail(t)} disabled={!!busy}
                  className="border border-primary/20 text-primary/80 rounded-full py-2 text-[11px] hover:bg-primary/10 disabled:opacity-50 capitalize">
                  {busy === "email" ? "…" : t.replace("_", " ")}
                </button>
              ))}
            </div>
            {(result || cover || email) && (
              <div className="mt-4 border border-primary/10 rounded-xl bg-black/30 overflow-hidden">
                <div className="flex border-b border-primary/10 overflow-x-auto no-scrollbar">
                  {(["resume", "cover", "email"] as const).filter((t) => t !== "cover" || cover).filter((t) => t !== "email" || email).map((t) => (
                    <button key={t} onClick={() => setPreview(t)}
                      className={`px-4 py-2 text-xs whitespace-nowrap ${preview === t ? "bg-primary/10 text-primary" : "text-primary/50"}`}>
                      {t === "resume" ? "Tailored resume" : t === "cover" ? "Cover letter" : "Email draft"}
                    </button>
                  ))}
                </div>
                {preview === "email" ? (
                  <pre className="p-4 max-h-[340px] overflow-y-auto text-xs text-primary/80 whitespace-pre-wrap">{email}</pre>
                ) : (
                  <div
                    className="p-4 max-h-[340px] overflow-y-auto text-xs leading-relaxed [&_h1]:text-lg [&_h1]:font-medium [&_h1]:text-[#E1E0CC] [&_h2]:text-sm [&_h2]:font-medium [&_h2]:text-primary [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:mt-3 [&_h3]:text-primary/80 [&_ul]:list-disc [&_ul]:pl-4 [&_p]:text-primary/80"
                    dangerouslySetInnerHTML={{ __html: markdownToHtml(preview === "resume" ? result!.tailored_resume_md : cover) }}
                  />
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* copilot sidebar */}
      <div className={`${cardCls} p-6 lg:col-span-3 h-fit`}>
        <div className="flex items-center gap-2 mb-4">
          <Bot className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-medium" style={{ color: "#E1E0CC" }}>Copilot</h3>
        </div>
        <CopilotChat applicationId={appId} />
      </div>
    </div>
  );
}

function MasterPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [stats, setStats] = useState<MasterStats | null>(null);
  const [experiences, setExperiences] = useState<MasterExperience[]>([]);
  const [projects, setProjects] = useState<MasterProject[]>([]);
  const [skills, setSkills] = useState<Record<string, string[]>>({});
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [importId, setImportId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, e, p, sk, rs] = await Promise.all([
        api.masterStats(), api.listMasterExperiences(),
        api.listMasterProjects(), api.listMasterSkills(), api.listResumes(),
      ]);
      setStats(s); setExperiences(e); setProjects(p); setSkills(sk); setResumes(rs);
    } catch { /* backend down */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function importFrom() {
    if (!importId) return toast("Pick a resume to import", true);
    setBusy("import");
    try {
      const res = await api.importMasterFromResume(Number(importId));
      toast(`Imported — ${res.imported.experiences} experiences, ${res.stats.projects} projects, ${res.imported.skills} skills`);
      refresh();
    } catch (e) { toast(e instanceof Error ? e.message : "Import failed", true); }
    finally { setBusy(null); }
  }

  async function deleteExp(id: number) {
    try { await api.del(`master/experiences/${id}`); refresh(); }
    catch { toast("Delete failed", true); }
  }

  async function deletePrj(id: number) {
    try { await api.del(`master/projects/${id}`); refresh(); }
    catch { toast("Delete failed", true); }
  }

  return (
    <div className="space-y-4">
      {/* stats + import */}
      <div className={cardCls + " p-6"}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Master CV database</h2>
          </div>
          {stats && (
            <div className="flex flex-wrap gap-2">
              {[
                [stats.experiences, "experiences"], [stats.projects, "projects"],
                [stats.skills, "skills"], [stats.certifications, "certs"],
              ].map(([n, label]) => (
                <span key={String(label)} className="text-xs px-3 py-1.5 rounded-full bg-primary/10 text-primary/80">
                  {n as number} {label as string}
                </span>
              ))}
            </div>
          )}
        </div>
        <p className="text-primary/50 text-xs mt-3 max-w-2xl">
          One detailed record of your whole career. Every tailored CV is <em className="font-serif italic">selected</em> from
          this database — top experiences and projects per job — never invented.
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <label htmlFor="master-import-select" className="text-xs text-primary/60">
            Import from an uploaded resume
          </label>
          <select id="master-import-select" className={inputCls + " max-w-xs"} value={importId} onChange={(e) => setImportId(e.target.value)}>
            <option value="">Choose a resume…</option>
            {resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <button onClick={importFrom} disabled={!!busy}
            className="bg-primary text-black rounded-full px-5 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2">
            {busy === "import" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />} Build master DB
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* experiences */}
        <div className={cardCls + " p-6"}>
          <h3 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-4">Experiences</h3>
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {experiences.length === 0 && <p className="text-primary/40 text-sm">Empty — import a resume above.</p>}
            {experiences.map((e) => (
              <div key={e.id} className="border border-primary/10 rounded-xl p-4 group">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-sm break-words" style={{ color: "#E1E0CC" }}>{e.title}</p>
                    <p className="text-primary/50 text-xs mt-0.5">{e.organization} · {e.start_date}–{e.end_date}</p>
                  </div>
                  <button onClick={() => deleteExp(e.id)} className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-primary/40 hover:text-red-400 transition-all shrink-0 min-w-[24px] min-h-[24px] flex items-center justify-center" aria-label={`Delete experience ${e.title}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {e.bullets.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {e.bullets.slice(0, 2).map((b, i) => (
                      <li key={i} className="text-primary/40 text-xs line-clamp-2">· {b}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* projects */}
        <div className={cardCls + " p-6"}>
          <h3 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-4">Projects</h3>
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {projects.length === 0 && <p className="text-primary/40 text-sm">Empty — import a resume above.</p>}
            {projects.map((p) => (
              <div key={p.id} className="border border-primary/10 rounded-xl p-4 group">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-sm break-words" style={{ color: "#E1E0CC" }}>{p.name}</p>
                    {p.tech && <p className="text-primary/50 text-xs mt-0.5 line-clamp-1">{p.tech}</p>}
                  </div>
                  <button onClick={() => deletePrj(p.id)} className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-primary/40 hover:text-red-400 transition-all shrink-0 min-w-[24px] min-h-[24px] flex items-center justify-center" aria-label={`Delete project ${p.name}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {p.bullets.length > 0 && (
                  <p className="text-primary/40 text-xs mt-2 line-clamp-2">{p.bullets[0]}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* skills */}
      <div className={cardCls + " p-6"}>
        <h3 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-4">Skills</h3>
        <div className="space-y-3">
          {Object.keys(skills).length === 0 && <p className="text-primary/40 text-sm">Empty — import a resume above.</p>}
          {Object.entries(skills).map(([category, names]) => (
            <div key={category}>
              <p className="text-[10px] text-primary/40 uppercase tracking-widest mb-1.5">{category}</p>
              <div className="flex flex-wrap gap-1.5">
                {names.map((n) => (
                  <span key={n} className="text-[11px] px-2.5 py-1 rounded-full bg-primary/10 text-primary/70">{n}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- panel: Applications ---------- */

function FitBreakdownBadge({ breakdown }: { breakdown: api.FitBreakdown | null | undefined }) {
  if (!breakdown) return <span className="text-primary/30 text-xs">—</span>;
  const cats = breakdown.categories;
  const categoryLabels: Record<string, string> = {
    hard_skills: "Hard skills",
    tools: "Tools",
    soft_skills: "Soft skills",
    certifications: "Certs",
    domain_keywords: "Domain",
  };
  return (
    <div className="flex flex-col gap-1 min-w-[160px]">
      {([
        { label: "Keyword", value: breakdown.keyword_match },
        { label: "Semantic", value: breakdown.semantic_similarity },
      ] as const).map(({ label, value }) => (
        <div key={label} className="flex items-center gap-1.5">
          <span className="text-[9px] text-primary/40 w-12 shrink-0">{label}</span>
          <div className="flex-1 h-1 bg-primary/10 rounded-full overflow-hidden">
            <div className="h-full bg-primary/60 rounded-full" style={{ width: `${Math.min(value, 100)}%` }} />
          </div>
          <span className="text-[9px] text-primary/50 w-7 text-right">{value.toFixed(0)}%</span>
        </div>
      ))}
      {cats && Object.entries(cats).map(([key, cat]) => {
        if (!cat || (cat.matched.length === 0 && cat.missing.length === 0)) return null;
        return (
          <div key={key} className="flex items-center gap-1.5">
            <span className="text-[9px] text-primary/40 w-12 shrink-0 truncate" title={categoryLabels[key] || key}>
              {categoryLabels[key] || key}
            </span>
            <div className="flex-1 h-1 bg-primary/10 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${cat.coverage >= 70 ? "bg-emerald-500/60" : cat.coverage >= 40 ? "bg-amber-500/60" : "bg-red-500/60"}`}
                style={{ width: `${cat.coverage}%` }}
              />
            </div>
            <span className="text-[9px] text-primary/50 w-7 text-right">{cat.coverage.toFixed(0)}%</span>
          </div>
        );
      })}
      {breakdown.missing_keywords.length > 0 && (
        <p className="text-[9px] text-amber-400/70 mt-0.5" title={`Missing: ${breakdown.missing_keywords.join(", ")}`}>
          Missing {breakdown.missing_keywords.length} skills
        </p>
      )}
    </div>
  );
}

function ApplicationsPanel() {
  const [apps, setApps] = useState<ApplicationRow[]>([]);
  const refresh = useCallback(async () => {
    try { setApps(await api.listApplications()); } catch { /* down */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className={cardCls}>
      <div className="flex items-center justify-between p-6 pb-4">
        <h3 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>Applications</h3>
        <button onClick={refresh} className="text-xs text-primary/60 hover:text-primary">Refresh</button>
      </div>
      <div className="overflow-x-auto">
        {apps.length === 0 ? (
          <p className="text-primary/40 text-sm px-6 pb-6">Nothing tailored yet — start in Tailor &amp; score.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-primary/40 text-[10px] uppercase tracking-widest">
                <th className="px-6 py-3 text-left font-medium">Role</th>
                <th className="px-4 py-3 text-left font-medium">Company</th>
                <th className="px-4 py-3 text-left font-medium">Resume</th>
                <th className="px-4 py-3 text-left font-medium">Fit breakdown</th>
                <th className="px-4 py-3 text-right font-medium">ATS</th>
                <th className="px-4 py-3 text-right font-medium">Δ</th>
                <th className="px-6 py-3 text-right font-medium">Files</th>
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => {
                const delta = (a.ats_after ?? 0) - (a.ats_before ?? 0);
                return (
                  <tr key={a.id} className="border-t border-primary/10">
                    <td className="px-6 py-3.5 font-medium" style={{ color: "#E1E0CC" }}>{a.jd_title}</td>
                    <td className="px-4 py-3.5 text-primary/60">{a.jd_company}</td>
                    <td className="px-4 py-3.5 text-primary/60">{a.resume_name}</td>
                    <td className="px-4 py-3.5"><FitBreakdownBadge breakdown={a.fit_breakdown} /></td>
                    <td className="px-4 py-3.5 text-right text-primary/80">{(a.ats_after ?? a.ats_before ?? 0).toFixed(1)}%</td>
                    <td className={`px-4 py-3.5 text-right font-medium ${delta >= 0 ? "text-primary" : "text-amber-300/70"}`}>
                      {delta >= 0 ? "+" : ""}{delta.toFixed(1)}
                    </td>
                    <td className="px-6 py-3.5 text-right space-x-3 whitespace-nowrap">
                      <a href={api.downloadUrl.resume(a.id)} target="_blank" className="text-xs text-primary/70 hover:text-primary">resume</a>
                      <a href={api.downloadUrl.cover(a.id)} target="_blank" className="text-xs text-primary/70 hover:text-primary">cover</a>
                      <a href={api.downloadUrl.latex(a.id)} target="_blank" className="text-xs text-primary/70 hover:text-primary">latex</a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ---------- panel: Settings ---------- */

const PROVIDERS = [
  { provider: "gemini", model: "gemini/gemini-3.6-flash", label: "Gemini 3.6 Flash", placeholder: "AIza..." },
  { provider: "groq", model: "groq/llama-3.3-70b-versatile", label: "Groq (Llama 3.3 70B)", placeholder: "gsk_..." },
  { provider: "ollama", model: "ollama/llama3.1", label: "Ollama (local, no key)", placeholder: "" },
];

function SettingsPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [chain, setChain] = useState<{ provider: string; model: string; api_key: string; api_key_set?: boolean; api_base?: string }[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.getLLMSettings().then((s) => {
      setChain(s.chain.map((c) => ({ ...c, api_key: "" })));
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  function setKey(model: string, value: string) {
    setKeys((prev) => ({ ...prev, [model]: value }));
  }

  function isConfigured(model: string) {
    return chain.some((c) => c.model === model && c.api_key_set);
  }

  async function save() {
    setBusy(true);
    try {
      const updates: { provider: string; model: string; api_key: string; api_base?: string }[] = [];
      for (const p of PROVIDERS) {
        const key = keys[p.model] || "";
        if (key || isConfigured(p.model)) {
          updates.push({ provider: p.provider, model: p.model, api_key: key });
        }
      }
      const result = await api.updateLLMSettings(updates);
      const cleared = result.chain.map((c) => ({ ...c, api_key: "" }));
      setChain(cleared);
      setKeys({});
      toast("LLM config saved — the agent will use your new keys on the next tailoring run");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Save failed", true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className={cardCls + " p-6"}>
        <div className="flex items-center gap-3 mb-4">
          <Settings className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>LLM API keys</h2>
        </div>
        <p className="text-primary/50 text-xs mb-6 max-w-2xl">
          Paste your API key below and hit Save. The agent needs at least one provider
          to tailor resumes with AI. If none are configured, the agent falls back
          to heuristic mode — it still works, just with less finesse.
        </p>

        <div className="space-y-4">
          {PROVIDERS.map((p) => {
            const configured = isConfigured(p.model);
            return (
              <div key={p.model} className="border border-primary/10 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium" style={{ color: "#E1E0CC" }}>{p.label}</p>
                    <p className="text-[10px] text-primary/40 mt-0.5">{p.model}</p>
                  </div>
                  {configured && (
                    <span className="text-[10px] px-2.5 py-1 rounded-full bg-primary/10 text-primary/80">
                      Key saved
                    </span>
                  )}
                </div>
                {p.placeholder ? (
                  <input
                    type="password"
                    className={inputCls}
                    placeholder={configured ? "•••••••• (leave blank to keep current)" : p.placeholder}
                    value={keys[p.model] || ""}
                    onChange={(e) => setKey(p.model, e.target.value)}
                  />
                ) : (
                  <p className="text-xs text-primary/40 italic">No key needed — runs locally via Ollama</p>
                )}
              </div>
            );
          })}
        </div>

        <button
          onClick={save}
          disabled={busy || Object.values(keys).every((v) => !v)}
          className="mt-6 bg-primary text-black rounded-full px-6 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          Save LLM config
        </button>

        <p className="text-[10px] text-primary/30 mt-3">
          Keys are stored in <code className="bg-primary/10 px-1.5 py-0.5 rounded">config/llm_config.yml</code> on the
          server. They are never sent to the browser except when you type them in this form.
        </p>
      </div>
    </div>
  );
}

/* ---------- panel: LinkedIn generator ---------- */

function LinkedInPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [headline, setHeadline] = useState("");
  const [about, setAbout] = useState("");
  const [busy, setBusy] = useState(false);
  const [generated, setGenerated] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const res = await api.generateLinkedIn();
      setHeadline(res.headline);
      setAbout(res.about);
      setGenerated(true);
      toast("LinkedIn copy generated from your Master CV");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Generation failed", true);
    } finally {
      setBusy(false);
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  }

  return (
    <div className="space-y-4">
      <div className={cardCls + " p-6"}>
        <div className="flex items-center gap-3 mb-4">
          <Link className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>LinkedIn profile copy</h2>
        </div>
        <p className="text-primary/50 text-xs mb-6 max-w-2xl">
          Generate a keyword-rich headline and an engaging About section from your
          Master CV database. Edit freely after generation.
        </p>
        <button onClick={generate} disabled={busy}
          className="bg-primary text-black rounded-full px-6 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          Generate from Master CV
        </button>
      </div>

      {generated && (
        <>
          <div className={cardCls + " p-6"}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-primary/80 uppercase tracking-widest">Headline</h3>
              <button onClick={() => copy(headline)} className="text-[10px] text-primary/50 hover:text-primary">Copy</button>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "#E1E0CC" }}>{headline}</p>
            <p className="text-[10px] text-primary/30 mt-2">{headline.length}/220 characters</p>
          </div>
          <div className={cardCls + " p-6"}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-primary/80 uppercase tracking-widest">About</h3>
              <button onClick={() => copy(about)} className="text-[10px] text-primary/50 hover:text-primary">Copy</button>
            </div>
            <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "#E1E0CC" }}>{about}</div>
            <p className="text-[10px] text-primary/30 mt-2">{about.length}/2600 characters</p>
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- console shell ---------- */

const TABS = [
  { id: "master", label: "Master CV" },
  { id: "resumes", label: "Resumes" },
  { id: "jds", label: "Job descriptions" },
  { id: "tailor", label: "Tailor & score" },
  { id: "applications", label: "Applications" },
  { id: "pipeline", label: "Pipeline" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "settings", label: "Settings" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function Console() {
  const [tab, setTab] = useState<TabId>("master");
  const [note, setNote] = useState<{ text: string; error?: boolean } | null>(null);
  const [user, setUser] = useState<{ name: string; email: string; picture: string } | null>(null);
  const [authState, setAuthState] = useState<"checking" | "open" | "locked" | "signed_in">("checking");
  const toast = useCallback((text: string, error?: boolean) => {
    setNote({ text, error });
    setTimeout(() => setNote(null), 3200);
  }, []);

  useEffect(() => {
    fetchMe()
      .then((me) => {
        if (!me.auth_enabled) setAuthState("open");
        else if (me.user) {
          setUser(me.user);
          setAuthState("signed_in");
        } else setAuthState("locked");
      })
      .catch(() => setAuthState("open")); // backend unreachable -> let panels show their own errors
  }, []);

  if (authState === "checking") {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-primary animate-spin" aria-label="Loading the Console" />
      </div>
    );
  }

  if (authState === "locked") {
    return <LoginScreen />;
  }

  return (
    <div className="min-h-screen bg-black p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* header */}
        <header className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/")} className="flex items-center gap-2 text-primary/60 hover:text-primary transition-colors text-sm py-1.5" aria-label="Back to ApplyJin landing page">
              <ArrowLeft className="w-4 h-4" aria-hidden="true" /> ApplyJin
            </button>
            <span className="text-primary/30" aria-hidden="true">/</span>
            <h1 className="text-lg font-medium" style={{ color: "#E1E0CC" }}>
              Console <span className="italic font-serif text-primary/70">where the agent works</span>
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2">
                {user.picture ? (
                  <img src={user.picture} alt="" className="w-7 h-7 rounded-full border border-primary/20" />
                ) : null}
                <span className="text-xs text-primary/70 hidden sm:inline max-w-[10rem] truncate">{user.name || user.email}</span>
                <button
                  onClick={() => { logout(() => { setUser(null); setAuthState("locked"); }); }}
                  className="text-xs px-3 py-1.5 rounded-full border border-primary/20 text-primary/70 hover:bg-primary/10 transition-colors min-h-[24px]"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <span className="text-[10px] px-3 py-1 rounded-full bg-primary/10 text-primary/70">self-learning agent</span>
            )}
          </div>
        </header>

        {/* tabs */}
        <nav className="flex gap-6 border-b border-primary/10 mb-8 overflow-x-auto no-scrollbar">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`pb-3 text-sm whitespace-nowrap transition-colors ${tab === t.id ? "text-primary font-medium border-b-2 border-primary -mb-px" : "text-primary/50 hover:text-primary/80"}`}>
              {t.label}
            </button>
          ))}
        </nav>

        {/* panel */}
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {tab === "master" && <MasterPanel toast={toast} />}
          {tab === "resumes" && <ResumesPanel toast={toast} />}
          {tab === "jds" && <JDsPanel toast={toast} />}
          {tab === "tailor" && <TailorPanel toast={toast} />}
          {tab === "applications" && <ApplicationsPanel />}
          {tab === "pipeline" && <KanbanBoard toast={toast} />}
          {tab === "linkedin" && <LinkedInPanel toast={toast} />}
          {tab === "settings" && <SettingsPanel toast={toast} />}
        </motion.div>

        <p className="text-center text-primary/30 text-xs mt-12 flex items-center justify-center gap-2">
          <ArrowRight className="w-3 h-3 -rotate-45" /> Every tailored fact traces back to your resume — the agent never invents.
        </p>
      </div>
      <Toast note={note} />
    </div>
  );
}
