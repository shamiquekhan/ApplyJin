import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Mail } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";

/**
 * Inquiries — the close. The product is live, so this is a direct
 * invitation to get in touch.
 */
export function Waitlist() {
  const reduce = useReducedMotion();

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
          The Console is live — build your master CV, tailor it to any
          posting, and download the LaTeX packet. Sign in with Google to
          keep your work yours.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8 md:mt-10">
          <motion.a
            href="/dashboard"
            className="w-fit flex items-center gap-2 bg-primary text-black rounded-full px-6 py-3 text-sm sm:text-base font-medium hover:opacity-90 transition-opacity"
            initial={reduce ? undefined : { y: 16, opacity: 0 }}
            whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            Open the Console
            <ArrowUpRight className="w-4 h-4" />
          </motion.a>
          <motion.a
            href="mailto:shamiquekhan18@gmail.com"
            className="w-fit flex items-center gap-2 border border-primary/30 text-primary rounded-full px-6 py-3 text-sm sm:text-base hover:bg-primary/10 transition-colors"
            initial={reduce ? undefined : { y: 16, opacity: 0 }}
            whileInView={reduce ? undefined : { y: 0, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <Mail className="w-4 h-4" />
            Get in touch
          </motion.a>
        </div>
      </div>
    </section>
  );
}
