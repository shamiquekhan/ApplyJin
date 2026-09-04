import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Dashboard", href: "/dashboard" },
      { label: "Learning loop", href: "#how-it-works" },
      { label: "Waitlist", href: "#inquiries" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "Documentation", href: "#how-it-works" },
      { label: "Guardrails", href: "#how-it-works" },
      { label: "API reference", href: "/docs" },
      { label: "Changelog", href: "#how-it-works" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "#how-it-works" },
      { label: "Careers", href: "#how-it-works" },
      { label: "Privacy", href: "#how-it-works" },
      { label: "Terms", href: "#how-it-works" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="bg-black p-4 md:p-6 pt-16 md:pt-24">
      <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-5 sm:px-6 md:px-10 py-12 md:py-16 max-w-full overflow-hidden">
        <div className="grid grid-cols-2 sm:grid-cols-12 gap-x-6 gap-y-10 md:gap-6">
          {/* Brand block */}
          <div className="col-span-2 sm:col-span-12 lg:col-span-5 flex flex-col gap-6 min-w-0">
            <motion.h2
              className="font-medium leading-[0.85] tracking-[-0.07em] text-[16vw] sm:text-[12vw] lg:text-[7vw] break-words"
              style={{ color: "#E1E0CC" }}
              initial={{ y: 20, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            >
              ApplyJin<span className="text-[0.31em] align-super">*</span>
            </motion.h2>
            <p className="text-primary/70 text-xs sm:text-sm max-w-sm" style={{ lineHeight: 1.4 }}>
              Auto-tailor + auto-fill, human clicks submit. The self-learning
              job application agent that never fabricates and never spams.
            </p>
            <a
              href="#inquiries"
              className="group inline-flex w-fit items-center gap-2 text-primary text-sm border border-primary/30 rounded-full px-5 py-2.5 hover:bg-primary hover:text-black transition-colors"
            >
              Join the waitlist
              <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </a>
          </div>

          {/* Link columns */}
          {COLUMNS.map((col) => (
            <div key={col.heading} className="col-span-1 sm:col-span-4 lg:col-span-2 min-w-0">
              <p className="text-[10px] sm:text-xs text-primary/50 uppercase tracking-widest mb-4">
                {col.heading}
              </p>
              <ul className="space-y-3">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm transition-colors break-words inline-block py-1"
                      style={{ color: "rgba(225, 224, 204, 0.8)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "#E1E0CC")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(225, 224, 204, 0.8)")}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 md:mt-16 pt-6 border-t border-primary/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <p className="text-[10px] sm:text-xs text-primary/50">
            © 2026 ApplyJin. All rights reserved.
          </p>
          <p className="text-[10px] sm:text-xs text-primary/50">
            Built with free tools — Gemini, LangGraph, Playwright, LaTeX.
          </p>
        </div>
      </div>
    </footer>
  );
}
