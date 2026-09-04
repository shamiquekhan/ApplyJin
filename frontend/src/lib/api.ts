/** Full API client for the ApplyJin backend (Hermes FastAPI).
 *
 * API base resolution:
 *  - dev/preview (npm run dev): "" -> Vite proxies /api to localhost:8000
 *  - production (Vercel): VITE_API_URL env var -> absolute Render URL
 */

import { API_BASE } from "./apiBase";
import { authHeader } from "./session";

export interface PublicStats {
  applications: number;
  interviews: number;
  response_rate: number;
  waitlist: number;
  style_guide_version: number | null;
  boards_supported: number;
  agents: number;
}

export interface ResumeSummary {
  id: number;
  name: string;
  skills: string[];
  created_at: string;
  preview: string;
}

export interface ResumeDetail extends ResumeSummary {
  content_md: string;
  raw_text: string;
}

export interface JDSummary {
  id: number;
  title: string;
  company: string;
  preview: string;
  created_at: string;
}

export interface KeywordBuckets {
  hard_skills: string[];
  soft_skills: string[];
  tools: string[];
  certifications: string[];
  domain_keywords: string[];
  extractor?: string;
}

export interface Scores {
  keyword_match: number;
  semantic_similarity: number;
  overall: number;
}

export interface TailorResult {
  tailored_resume_md: string;
  scores_after: Scores;
  delta: { overall: number; keyword_match: number; semantic: number };
  guardrail_violations: string[];
  validated: boolean;
  model_used: string;
}

export interface ApplicationRow {
  id: number;
  status: string;
  ats_before: number | null;
  ats_after: number | null;
  kw_before?: number | null;
  kw_after?: number | null;
  created_at: string;
  resume_name: string;
  jd_title: string;
  jd_company: string;
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let message = `Request failed (${r.status})`;
    try {
      const body = await r.json();
      message = body.detail || body.message || message;
    } catch {
      /* non-JSON error */
    }
    throw new Error(message);
  }
  return r.json() as Promise<T>;
}

function form(data: Record<string, string | Blob>): FormData {
  const fd = new FormData();
  Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  return fd;
}

// -------- public (landing)
export const fetchStats = () =>
  fetch(`${API_BASE}/api/public/stats`, { headers: authHeader() }).then((r) => handle<PublicStats>(r));

// -------- resumes
export const listResumes = () =>
  fetch(`${API_BASE}/api/resumes`, { headers: authHeader() }).then((r) => handle<ResumeSummary[]>(r));

export const getResume = (id: number) =>
  fetch(`${API_BASE}/api/resumes/${id}`, { headers: authHeader() }).then((r) => handle<ResumeDetail>(r));

export const uploadResume = (file: File, name: string) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", name || file.name);
  return fetch(`${API_BASE}/api/resumes/upload`, { method: "POST", body: fd, ...authHeader() })
    .then((r) => handle<{ id: number; bullets: number }>(r));
};

export const createResume = (name: string, content: string) =>
  fetch(`${API_BASE}/api/resumes/create`, { method: "POST", body: form({ name, content, ...authHeader() }) })
    .then((r) => handle<{ id: number }>(r));

// -------- job descriptions
export const listJDs = () =>
  fetch(`${API_BASE}/api/job-descriptions`, { headers: authHeader() }).then((r) => handle<JDSummary[]>(r));

export const addJD = (title: string, company: string, content: string) =>
  fetch(`${API_BASE}/api/job-descriptions`, { method: "POST", body: form({ title, company, content, ...authHeader() }) })
    .then((r) => handle<{ id: number }>(r));

export const extractKeywords = (jdId: number) =>
  fetch(`${API_BASE}/api/job-descriptions/${jdId}/extract-keywords`, { method: "POST", ...authHeader() })
    .then((r) => handle<KeywordBuckets>(r));

// -------- applications
export const createApplication = (resumeId: number, jdId: number) =>
  fetch(`${API_BASE}/api/applications`, { method: "POST", body: form({ resume_id: String(resumeId), jd_id: String(jdId), ...authHeader() }) })
    .then((r) => handle<{ id: number; scores_before: Scores }>(r));

export const tailorResume = (appId: number, keywords: string[]) =>
  fetch(`${API_BASE}/api/applications/${appId}/tailor`, {
    ...authHeader(),
    method: "POST",
    body: form({ selected_keywords: JSON.stringify(keywords) }),
  }).then((r) => handle<TailorResult>(r));

export const generateCoverLetter = (appId: number) =>
  fetch(`${API_BASE}/api/applications/${appId}/cover-letter`, { method: "POST", ...authHeader() })
    .then((r) => handle<{ cover_letter_md: string }>(r));

export const listApplications = () =>
  fetch(`${API_BASE}/api/applications`, { headers: authHeader() }).then((r) => handle<ApplicationRow[]>(r));

export const downloadUrl = {
  resume: (id: number) => `${API_BASE}/api/applications/${id}/download-resume`,
  cover: (id: number) => `${API_BASE}/api/applications/${id}/download-cover-letter`,
  latex: (id: number) => `${API_BASE}/api/applications/${id}/download-resume-latex`,
};

/** DELETE request against the configured API base. */
export const del = (path: string) =>
  fetch(`${API_BASE}/api/${path}`, { method: "DELETE", ...authHeader() });

// -------- master CV database
export interface MasterProfile {
  full_name?: string; email?: string; phone?: string; location?: string;
  linkedin?: string; github?: string; website?: string;
  headline?: string; summary?: string; years_experience?: number;
}

export interface MasterExperience {
  id: number; title: string; organization: string; location: string;
  start_date: string; end_date: string; description: string;
  bullets: string[]; tags: string;
}

export interface MasterProject {
  id: number; name: string; tech: string; description: string;
  bullets: string[]; link: string; tags: string;
}

export interface MasterStats {
  experiences: number; projects: number; education: number;
  certifications: number; skills: number; profile_complete: boolean;
}

export const masterProfile = () =>
  fetch(`${API_BASE}/api/master/profile`, { headers: authHeader() }).then((r) => handle<MasterProfile>(r));

export const updateMasterProfile = (profile: Partial<MasterProfile>) =>
  fetch(`${API_BASE}/api/master/profile`, {
    ...authHeader(),
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  }).then((r) => handle<MasterProfile>(r));

export const masterStats = () =>
  fetch(`${API_BASE}/api/master/stats`, { headers: authHeader() }).then((r) => handle<MasterStats>(r));

export const listMasterExperiences = () =>
  fetch(`${API_BASE}/api/master/experiences`, { headers: authHeader() }).then((r) => handle<MasterExperience[]>(r));

export const listMasterProjects = () =>
  fetch(`${API_BASE}/api/master/projects`, { headers: authHeader() }).then((r) => handle<MasterProject[]>(r));

export const listMasterSkills = () =>
  fetch(`${API_BASE}/api/master/skills`, { headers: authHeader() }).then((r) => handle<Record<string, string[]>>(r));

export const importMasterFromResume = (resumeId: number) =>
  fetch(`${API_BASE}/api/master/import-resume`, {
    ...authHeader(),
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_id: resumeId }),
  }).then((r) => handle<{ imported: Record<string, number>; stats: MasterStats }>(r));

// -------- tailor v3 additions
export interface SelectionEntry {
  kind: string; title: string; score: number; matched_keywords: string[];
}

export interface TailorResultV3 extends TailorResult {
  selection: SelectionEntry[];
  skill_selection: string[];
  gaps: string[];
}

export const tailorResumeV3 = (appId: number, keywords: string[]) =>
  fetch(`${API_BASE}/api/applications/${appId}/tailor`, {
    ...authHeader(),
    method: "POST",
    body: form({ selected_keywords: JSON.stringify(keywords) }),
  }).then((r) => handle<TailorResultV3>(r));

export const emailTemplate = (appId: number, templateType: string) =>
  fetch(`${API_BASE}/api/applications/${appId}/email-template`, {
    ...authHeader(),
    method: "POST",
    body: form({ template_type: templateType }),
  }).then((r) => handle<{ email_md: string; hiring_manager?: string; emails: string[] }>(r));
