import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import * as api from "../lib/api";
import type { PipelineCard, PipelineStatus } from "../lib/api";

const COLUMNS: { status: PipelineStatus; label: string; color: string }[] = [
  { status: "saved", label: "Saved", color: "bg-primary/20 text-primary" },
  { status: "tailored", label: "Tailored", color: "bg-blue-500/20 text-blue-300" },
  { status: "applied", label: "Applied", color: "bg-amber-500/20 text-amber-300" },
  { status: "interviewing", label: "Interviewing", color: "bg-purple-500/20 text-purple-300" },
  { status: "offer", label: "Offer", color: "bg-emerald-500/20 text-emerald-300" },
  { status: "rejected", label: "Rejected", color: "bg-red-500/20 text-red-300" },
  { status: "ghosted", label: "Ghosted", color: "bg-gray-500/20 text-gray-400" },
];

function Card({ card, onMove }: { card: PipelineCard; onMove: (id: number, status: PipelineStatus) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <motion.div
      layout
      className="bg-[#1a1a1a] border border-primary/10 rounded-xl p-3 cursor-pointer hover:border-primary/30 transition-colors"
      onClick={() => setOpen(!open)}
    >
      <p className="text-xs font-medium truncate" style={{ color: "#E1E0CC" }}>{card.jd_title}</p>
      <p className="text-[10px] text-primary/50 mt-0.5 truncate">{card.jd_company}</p>
      {card.ats_after != null && (
        <p className="text-[10px] text-primary/40 mt-1">ATS {card.ats_after.toFixed(0)}%</p>
      )}
      {open && (
        <div className="mt-2 pt-2 border-t border-primary/10">
          <p className="text-[10px] text-primary/40 mb-1.5">Move to:</p>
          <div className="flex flex-wrap gap-1">
            {COLUMNS.filter((c) => c.status !== card.pipeline_status).map((col) => (
              <button
                key={col.status}
                onClick={(e) => { e.stopPropagation(); onMove(card.id, col.status); setOpen(false); }}
                className={`text-[9px] px-2 py-0.5 rounded-full ${col.color} hover:opacity-80 transition-opacity`}
              >
                {col.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

export function KanbanBoard({ toast }: { toast: (t: string, error?: boolean) => void }) {
  const [pipeline, setPipeline] = useState<Record<PipelineStatus, PipelineCard[]> | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setPipeline(await api.getPipeline());
    } catch { /* backend down */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const moveCard = useCallback(async (appId: number, status: PipelineStatus) => {
    setBusy(true);
    try {
      await api.updatePipelineStatus(appId, status);
      toast(`Moved to ${status}`);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Move failed", true);
    } finally {
      setBusy(false);
    }
  }, [refresh, toast]);

  if (!pipeline) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 text-primary animate-spin" />
      </div>
    );
  }

  const total = Object.values(pipeline).reduce((s, col) => s + col.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-primary/50">{total} application{total !== 1 ? "s" : ""} in pipeline</p>
        <button onClick={refresh} className="text-xs text-primary/60 hover:text-primary">Refresh</button>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-4 no-scrollbar">
        {COLUMNS.map((col) => {
          const cards = pipeline[col.status] || [];
          return (
            <div key={col.status} className="min-w-[200px] flex-1">
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${col.color}`}>
                  {col.label}
                </span>
                <span className="text-[10px] text-primary/30">{cards.length}</span>
              </div>
              <div className="space-y-2 min-h-[80px]">
                {cards.length === 0 && (
                  <p className="text-[10px] text-primary/20 text-center py-4">Empty</p>
                )}
                {cards.map((card) => (
                  <Card key={card.id} card={{ ...card, pipeline_status: col.status }} onMove={moveCard} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
