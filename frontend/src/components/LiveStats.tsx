import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { fetchStats, PublicStats } from "../lib/api";

/**
 * A quiet strip of live numbers from the running agent — proof the
 * product exists, not decoration. Renders nothing until real data
 * arrives, and shows nothing if the backend is unreachable (the
 * landing page works standalone).
 */
export function LiveStats() {
  const [stats, setStats] = useState<PublicStats | null>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    let cancelled = false;
    fetchStats()
      .then((s) => !cancelled && setStats(s))
      .catch(() => undefined); // offline = hide the strip
    return () => {
      cancelled = true;
    };
  }, []);

  if (!stats) return null;

  const facts = [
    { value: String(stats.applications), label: "applications tailored this month" },
    { value: `${Math.round(stats.response_rate * 100)}%`, label: "of them heard back" },
    { value: String(stats.interviews), label: "interviews booked" },
    { value: String(stats.boards_supported), label: "job boards scouted daily" },
  ];

  return (
    <section className="bg-black px-4 md:px-6 py-10 md:py-14">
      <motion.div
        className="max-w-6xl mx-auto flex flex-wrap items-baseline justify-center gap-x-10 gap-y-6 md:gap-x-16"
        initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        {facts.map((fact) => (
          <div key={fact.label} className="flex items-baseline gap-3">
            <span
              className="text-3xl sm:text-4xl md:text-5xl font-light tracking-tight"
              style={{ color: "#E1E0CC" }}
            >
              {fact.value}
            </span>
            <span className="text-primary/70 text-xs sm:text-sm max-w-[9rem] leading-snug">
              {fact.label}
            </span>
          </div>
        ))}
      </motion.div>
    </section>
  );
}
