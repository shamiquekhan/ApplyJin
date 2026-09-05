import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { WordsPullUp } from "./WordsPullUp";

const NAV_ITEMS = ["How it works", "Dashboard", "Learning loop", "Inquiries"];

export function Hero() {
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
            {NAV_ITEMS.map((item) => {
              const href = item === "Dashboard"
                ? "/dashboard"
                : item === "Inquiries"
                  ? "mailto:shamiquekhan18@gmail.com"
                  : `#${item.toLowerCase().replace(/\s+/g, "-")}`;
              return (
                <a
                  key={item}
                  href={href}
                  className="text-[10px] sm:text-xs md:text-sm transition-colors shrink-0 min-h-[24px] flex items-center"
                  style={{ color: "rgba(225, 224, 204, 0.8)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#E1E0CC")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(225, 224, 204, 0.8)")}
                >
                  {item}
                </a>
              );
            })}
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

            {/* Right 4 cols: description + CTA straight to the Console */}
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

              <motion.a
                href="/dashboard"
                className="group inline-flex w-fit items-center gap-2 bg-primary rounded-full py-2 pl-5 pr-2 hover:gap-3 transition-all"
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
              >
                <span className="text-black font-medium text-sm sm:text-base">
                  Open the Console
                </span>
                <span className="bg-black rounded-full w-9 h-9 sm:w-10 sm:h-10 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <ArrowRight className="w-4 h-4 text-primary" />
                </span>
              </motion.a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
