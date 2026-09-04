import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { joinWaitlist } from "../lib/api";
import { WordsPullUpMultiStyle } from "./WordsPullUp";

/**
 * Inquiries — the waitlist close. One big serif-italic moment in the
 * established identity, with a working form backed by the agent's
 * SQLite waitlist.
 */
export function Waitlist() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [note, setNote] = useState("");
  const reduceMotion = useReducedMotion();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("sending");
    try {
      const result = await joinWaitlist(email);
      setNote(result.message);
      setStatus("done");
      setEmail("");
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Something went wrong. Try again.");
      setStatus("error");
    }
  }

  return (
    <section id="inquiries" className="bg-black p-4 md:p-6 py-16 md:py-24">
      <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
        <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
          <WordsPullUpMultiStyle
            segments={[
              { text: "Let the agent apply", className: "font-normal" },
              { text: "while you sleep.", className: "italic font-serif" },
            ]}
          />
        </h2>
        <p className="text-primary/70 text-xs sm:text-sm md:text-base max-w-xl mx-auto mt-6 md:mt-8">
          Join the waitlist and get first access to the ApplyJin beta.
          No spam — one email when your invite is ready.
        </p>

        <motion.form
          onSubmit={submit}
          className="mt-8 md:mt-10 mx-auto w-full max-w-md"
          initial={reduceMotion ? undefined : { y: 16, opacity: 0 }}
          whileInView={reduceMotion ? undefined : { y: 0, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex items-center gap-2 bg-primary rounded-full pl-5 pr-2 py-2">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={status === "sending" || status === "done"}
              aria-label="Email address"
              className="flex-1 bg-transparent outline-none text-black placeholder-black/50 text-sm sm:text-base min-w-0"
            />
            <button
              type="submit"
              disabled={status === "sending" || status === "done"}
              className="bg-black rounded-full w-10 h-10 flex items-center justify-center shrink-0 hover:scale-110 transition-transform disabled:opacity-60"
              aria-label="Join the waitlist"
            >
              {status === "done" ? (
                <Check className="w-4 h-4 text-primary" />
              ) : (
                <ArrowRight className="w-4 h-4 text-primary" />
              )}
            </button>
          </div>
          <AnimatePresence>
            {note && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`mt-3 text-xs sm:text-sm ${
                  status === "error" ? "text-red-400" : "text-primary/80"
                }`}
              >
                {note}
              </motion.p>
            )}
          </AnimatePresence>
        </motion.form>
      </div>
    </section>
  );
}
