import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { WordsPullUp } from "./WordsPullUp";
import { joinWaitlist } from "../lib/api";

const NAV_ITEMS = ["How it works", "Dashboard", "Learning loop", "Inquiries"];

export function Hero() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [note, setNote] = useState("");

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
    <section id="how-it-works" className="h-screen p-4 md:p-6">
      <div className="relative h-full w-full rounded-2xl md:rounded-[2rem] overflow-hidden">
        {/* Background video — decorative, muted, hidden from screen readers */}
        <video
          className="absolute inset-0 h-full w-full object-cover"
          autoPlay
          loop
          muted
          playsInline
          aria-hidden="true"
          tabIndex={-1}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_170732_8a9ccda6-5cff-4628-b164-059c500a2b41.mp4"
        />

        {/* Noise overlay on video */}
        <div className="noise-overlay absolute inset-0 opacity-[0.7] mix-blend-overlay pointer-events-none" />

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/60" />

        {/* Navbar — black pill hanging from the top edge */}
        <nav className="absolute top-0 left-1/2 -translate-x-1/2 z-10 bg-black rounded-b-2xl md:rounded-b-3xl px-4 py-2 md:px-8 w-[calc(100%-2rem)] max-w-2xl" aria-label="Main">
          <div className="flex items-center justify-center gap-3 sm:gap-6 md:gap-12 lg:gap-14 overflow-x-auto no-scrollbar">
            <a
              href="/"
              className="text-[10px] sm:text-xs md:text-sm font-bold tracking-tight shrink-0 min-h-[24px] flex items-center"
              style={{ color: "#E1E0CC" }}
            >
              ApplyJin
            </a>
            {NAV_ITEMS.map((item) => (
              <a
                key={item}
                href={
                  item === "Dashboard"
                    ? "/dashboard"
                    : `#${item.toLowerCase().replace(/\s+/g, "-")}`
                }
                className="text-[10px] sm:text-xs md:text-sm transition-colors shrink-0 min-h-[24px] flex items-center"
                style={{ color: "rgba(225, 224, 204, 0.8)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#E1E0CC")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(225, 224, 204, 0.8)")}
              >
                {item}
              </a>
            ))}
          </div>
        </nav>

        {/* Hero content — bottom aligned */}
        <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6 lg:p-8">
          <div className="grid grid-cols-12 items-end gap-4">
            {/* Left 8 cols: giant heading — sized for an 8-char wordmark */}
            <div className="col-span-12 lg:col-span-8 pr-4 lg:pr-8 overflow-hidden">
              <h1 className="font-medium leading-[0.85] tracking-[-0.07em] text-[17.5vw] sm:text-[16.5vw] md:text-[15vw] lg:text-[13vw] xl:text-[12.5vw] 2xl:text-[13vw] break-words">
                <WordsPullUp text="ApplyJin" showAsterisk />
              </h1>
            </div>

            {/* Right 4 cols: description + waitlist */}
            <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 md:gap-6">
              <motion.p
                className="text-primary/70 text-xs sm:text-sm md:text-base"
                style={{ lineHeight: 1.2 }}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                ApplyJin is a self-learning application agent that scouts
                jobs, tailors your resume to every posting, drafts cover
                letters and tracks outcomes — while you keep the final
                say on every submit.
              </motion.p>

              {/* Waitlist — replaces dead CTA with a working form */}
              <motion.form
                onSubmit={submit}
                className="w-full max-w-md"
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="flex items-center gap-2 bg-primary rounded-full pl-5 pr-2 py-2">
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    disabled={status === "sending" || status === "done"}
                    aria-label="Email for the ApplyJin waitlist"
                    className="flex-1 bg-transparent outline-none text-black placeholder-black/50 text-sm sm:text-base min-w-0"
                  />
                  <button
                    type="submit"
                    disabled={status === "sending" || status === "done"}
                    className="bg-black rounded-full w-9 h-9 sm:w-10 sm:h-10 flex items-center justify-center shrink-0 hover:scale-110 transition-transform disabled:opacity-60"
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
                      className={`mt-2 text-xs px-2 ${
                        status === "error" ? "text-red-400" : "text-primary/80"
                      }`}
                    >
                      {note}
                    </motion.p>
                  )}
                </AnimatePresence>
              </motion.form>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
