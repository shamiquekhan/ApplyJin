import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Building2, Check, DollarSign, Info, Loader2, Search, Shield, ShieldAlert, ShieldCheck, ShieldQuestion, TrendingUp } from "lucide-react";
import * as api from "../lib/api";

const cardCls = "bg-card border border-primary/10 rounded-xl";

function VisaBadge({ result }: { result: api.VisaSponsorship }) {
  const styles: Record<string, { icon: typeof Shield; color: string; label: string }> = {
    yes: { icon: ShieldCheck, color: "text-emerald-400", label: "Sponsors" },
    likely_yes: { icon: Shield, color: "text-blue-400", label: "Likely sponsors" },
    no: { icon: ShieldAlert, color: "text-red-400", label: "No sponsorship" },
    likely_no: { icon: ShieldAlert, color: "text-amber-400", label: "Likely no sponsorship" },
    unknown: { icon: ShieldQuestion, color: "text-gray-400", label: "Unknown" },
  };
  const s = styles[result.sponsorship] || styles.unknown;
  const Icon = s.icon;
  return (
    <div className={`${cardCls} p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-5 h-5 ${s.color}`} />
        <span className={`text-sm font-medium ${s.color}`}>{s.label}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-primary/50">
        <span>Confidence: {(result.confidence * 100).toFixed(0)}%</span>
        <span>Method: {result.method}</span>
        {result.cached && <span className="text-primary/30">(cached)</span>}
      </div>
      {result.evidence.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {result.evidence.map((e, i) => (
            <span key={i} className="text-[10px] bg-primary/5 text-primary/50 px-2 py-0.5 rounded-full">{e}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function SalaryCard({ result }: { result: api.SalaryInsights }) {
  const fmt = (n: number) => `$${(n / 1000).toFixed(0)}k`;
  return (
    <div className={`${cardCls} p-4`}>
      <div className="flex items-center gap-2 mb-3">
        <DollarSign className="w-5 h-5 text-emerald-400" />
        <span className="text-sm font-medium text-emerald-400">Salary range</span>
      </div>
      <div className="flex items-end gap-4 mb-2">
        <div>
          <p className="text-[10px] text-primary/40 uppercase">Min</p>
          <p className="text-lg font-medium text-primary/80">{fmt(result.min)}</p>
        </div>
        <div>
          <p className="text-[10px] text-primary/40 uppercase">Median</p>
          <p className="text-xl font-bold text-primary">{fmt(result.median)}</p>
        </div>
        <div>
          <p className="text-[10px] text-primary/40 uppercase">Max</p>
          <p className="text-lg font-medium text-primary/80">{fmt(result.max)}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-primary/50 mt-2">
        <span>Source: {result.source.replace("_", " ")}</span>
        {result.sample_size && <span>n={result.sample_size}</span>}
        {result.level && <span>Level: {result.level}</span>}
        {result.location_multiplier && result.location_multiplier !== 1.0 && (
          <span>Location ×{result.location_multiplier}</span>
        )}
      </div>
    </div>
  );
}

export function ResearchPanel({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [visaResult, setVisaResult] = useState<api.VisaSponsorship | null>(null);
  const [salaryResult, setSalaryResult] = useState<api.SalaryInsights | null>(null);
  const [busy, setBusy] = useState(false);

  const lookupVisa = useCallback(async () => {
    if (!company) return toast("Enter a company name", true);
    setBusy(true);
    try {
      const res = await api.getVisaSponsorship(company);
      setVisaResult(res);
      toast("Visa sponsorship lookup complete");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Lookup failed", true);
    } finally {
      setBusy(false);
    }
  }, [company, toast]);

  const lookupSalary = useCallback(async () => {
    if (!title) return toast("Enter a job title", true);
    setBusy(true);
    try {
      const res = await api.getSalaryInsights(title, location, company);
      setSalaryResult(res);
      toast("Salary insights loaded");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Lookup failed", true);
    } finally {
      setBusy(false);
    }
  }, [title, location, company, toast]);

  const markSponsor = useCallback(async (sponsorship: string) => {
    if (!company) return;
    setBusy(true);
    try {
      await api.addVisaSponsor(company, sponsorship, "user confirmed");
      toast(`Marked ${company} as ${sponsorship}`);
      lookupVisa();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed", true);
    } finally {
      setBusy(false);
    }
  }, [company, toast, lookupVisa]);

  return (
    <div className="space-y-4">
      {/* Lookup form */}
      <div className={`${cardCls} p-6`}>
        <h2 className="text-sm font-medium text-primary/80 uppercase tracking-widest mb-4 flex items-center gap-2">
          <Search className="w-4 h-4" />
          Research lookup
        </h2>
        <div className="grid grid-cols-3 gap-3">
          <input
            className="input"
            placeholder="Company name"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
          <input
            className="input"
            placeholder="Job title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="input"
            placeholder="Location (optional)"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </div>
        <div className="flex gap-3 mt-3">
          <button onClick={lookupVisa} disabled={busy || !company}
            className="bg-primary text-black rounded-full px-5 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            <Shield className="w-4 h-4" /> Visa lookup
          </button>
          <button onClick={lookupSalary} disabled={busy || !title}
            className="bg-primary text-black rounded-full px-5 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            <TrendingUp className="w-4 h-4" /> Salary lookup
          </button>
        </div>
      </div>

      {/* Results */}
      {visaResult && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <VisaBadge result={visaResult} />
          {visaResult.sponsorship === "unknown" && (
            <div className="mt-2 flex gap-2">
              <button onClick={() => markSponsor("yes")} className="text-[10px] text-emerald-400 hover:underline">+ Mark as sponsor</button>
              <button onClick={() => markSponsor("no")} className="text-[10px] text-red-400 hover:underline">+ Mark as no sponsorship</button>
            </div>
          )}
        </motion.div>
      )}

      {salaryResult && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <SalaryCard result={salaryResult} />
        </motion.div>
      )}

      {/* Info */}
      {!visaResult && !salaryResult && (
        <div className={`${cardCls} p-6 flex items-start gap-3`}>
          <Info className="w-5 h-5 text-primary/30 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-primary/60">
              Enter a company and job title to look up visa sponsorship history and
              estimated salary ranges. Visa data comes from DOL OFLC records and
              known sponsor lists. Salary data comes from Adzuna's free-tier API
              and BLS Occupational Employment Statistics.
            </p>
            <p className="text-xs text-primary/40 mt-2">
              You can manually correct sponsorship status — the lookup will cache
              your corrections for future searches.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
