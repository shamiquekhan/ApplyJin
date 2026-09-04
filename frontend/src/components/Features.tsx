import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { Check, ArrowRight } from "lucide-react";
import { WordsPullUpMultiStyle } from "./WordsPullUp";

const VIDEO_URL =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260406_133058_0504132a-0cf3-4450-a370-8ea3b05c95d4.mp4";

const CARDS = [
  {
    number: "01",
    title: "Job Scout.",
    icon: "https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171918_4a5edc79-d78f-4637-ac8b-53c43c220606.png&w=1280&q=85",
    items: [
      { title: "Eight job boards, one search", desc: "LinkedIn, Indeed, Glassdoor and more, deduplicated automatically." },
      { title: "Greenhouse + Lever APIs", desc: "Public ATS endpoints — no scraping, no blocking." },
      { title: "Freshness filters", desc: "Only postings from the last 14 days hit your queue." },
      { title: "Fuzzy deduplication", desc: "Same role on three boards? One application, never three." },
    ],
  },
  {
    number: "02",
    title: "Smart Tailoring.",
    icon: "https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171741_ed9845ab-f5b2-4018-8ce7-07cc01823522.png&w=1280&q=85",
    items: [
      { title: "RAG-grounded rewrites", desc: "Every bullet traces back to your real experience library." },
      { title: "Fabrication guardrails", desc: "Invented skills, dates or companies are flagged before you see them." },
      { title: "ATS before/after scores", desc: "Watch the keyword match climb on every tailored variant." },
    ],
  },
  {
    number: "03",
    title: "Learning Loop.",
    icon: "https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171809_f56666dc-c099-4778-ad82-9ad4f209567b.png&w=1280&q=85",
    items: [
      { title: "Outcome triage", desc: "Interview and rejection emails feed the tracker automatically." },
      { title: "A/B style testing", desc: "Chi-squared verdicts on which phrasing wins callbacks." },
      { title: "Versioned style guides", desc: "Learned patterns roll into the tailor, fully rollback-able." },
    ],
  },
];

function FeatureCard({ card, index }: { card: (typeof CARDS)[number]; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <div
      ref={ref}
      className="bg-[#212121] rounded-2xl md:rounded-[1.5rem] p-5 md:p-6 flex flex-col h-full"
    >
      <motion.div
        className="flex flex-col h-full gap-6"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={inView ? { scale: 1, opacity: 1 } : {}}
        transition={{
          duration: 0.7,
          delay: index * 0.15,
          ease: [0.22, 1, 0.36, 1],
        }}
      >
        <img
          src={card.icon}
          alt=""
          className="w-10 h-10 sm:w-12 sm:h-12 rounded object-cover"
        />

        <h3 className="text-xl sm:text-2xl font-medium mt-auto" style={{ color: "#E1E0CC" }}>
          <span className="text-primary/60 text-sm font-normal mr-2 align-top">
            ({card.number})
          </span>
          {card.title}
        </h3>

        <ul className="space-y-3 md:space-y-4">
          {card.items.map((item) => (
            <li key={item.title} className="flex items-start gap-3">
              <Check className="w-4 h-4 text-primary shrink-0 mt-0.5" />
              <div>
                <p className="text-primary text-sm font-medium">{item.title}</p>
                <p className="text-gray-300 text-xs sm:text-sm mt-0.5 leading-snug">{item.desc}</p>
              </div>
            </li>
          ))}
        </ul>

        <a
          href="#how-it-works"
          className="inline-flex items-center gap-2 text-primary text-sm mt-auto pt-2 group"
        >
          Learn more
          <ArrowRight className="w-4 h-4 -rotate-45 group-hover:translate-x-1 transition-transform" />
        </a>
      </motion.div>
    </div>
  );
}

export function Features() {
  return (
    <section className="min-h-screen bg-black relative p-4 md:p-6 py-16 md:py-24">
      {/* Subtle noise background */}
      <div className="bg-noise absolute inset-0 opacity-[0.15] pointer-events-none" />

      <div className="relative">
        <div className="max-w-5xl mx-auto text-center mb-10 md:mb-16">
          <WordsPullUpMultiStyle
            segments={[
              { text: "Studio-grade workflows for ambitious applicants.", className: "" },
            ]}
            className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-normal"
          />
          <div className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-normal text-primary/50 mt-2">
            <WordsPullUpMultiStyle
              segments={[
                { text: "Built for your career. Powered by agents.", className: "" },
              ]}
              className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-normal text-primary/50"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-3 lg:gap-3 lg:h-[480px] auto-rows-fr">
          {/* Card 1: video card */}
          <VideoCard />

          {CARDS.map((card, i) => (
            <FeatureCard key={card.number} card={card} index={i + 1} />
          ))}
        </div>
      </div>
    </section>
  );
}

function VideoCard() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <div ref={ref} className="rounded-2xl md:rounded-[1.5rem] overflow-hidden relative h-64 md:h-full">
      <motion.div
        className="h-full"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={inView ? { scale: 1, opacity: 1 } : {}}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        <video
          className="absolute inset-0 h-full w-full object-cover"
          autoPlay
          loop
          muted
          playsInline
          aria-hidden="true"
          tabIndex={-1}
          src={VIDEO_URL}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
        <p
          className="absolute bottom-4 left-5 right-5 text-sm sm:text-base"
          style={{ color: "#E1E0CC" }}
        >
          Your career canvas.
        </p>
      </motion.div>
    </div>
  );
}
