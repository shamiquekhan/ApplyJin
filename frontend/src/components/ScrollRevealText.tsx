import { useRef } from "react";
import { motion, useScroll, useTransform, MotionValue } from "framer-motion";

interface AnimatedLetterProps {
  char: string;
  index: number;
  totalChars: number;
  progress: MotionValue<number>;
}

function AnimatedLetter({ char, index, totalChars, progress }: AnimatedLetterProps) {
  const charProgress = index / totalChars;
  const opacity = useTransform(
    progress,
    [charProgress - 0.1, charProgress + 0.05],
    [0.2, 1]
  );
  // Spaces use non-breaking space so they never collapse; rendered as a
  // plain span (not motion.span) to avoid initial-paint flicker where
  // animated opacity starts at 0.2 — invisible on dark backgrounds.
  if (char === " ") {
    return <span style={{ opacity }} className="inline-block">&nbsp;</span>;
  }
  return <motion.span style={{ opacity }}>{char}</motion.span>;
}

interface ScrollRevealTextProps {
  text: string;
  className?: string;
}

/**
 * Paragraph where each character's opacity transitions from 0.2 to 1
 * based on scroll position, creating a progressive text reveal.
 *
 * Layout-safe: white-space: pre preserves natural word boundaries so the
 * text wraps at the right spots, and non-breaking spaces (\u00A0) prevent
 * the per-character spans from collapsing spaces on initial paint.
 */
export function ScrollRevealText({ text, className }: ScrollRevealTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.8", "end 0.2"],
  });

  let charCount = 0;
  const totalChars = text.length;

  return (
    <p
      ref={ref}
      className={className}
      style={{ maxWidth: "100%", overflowWrap: "break-word", whiteSpace: "pre-wrap" }}
    >
      {text.split("").map((char, i) => {
        const index = charCount++;
        return (
          <AnimatedLetter
            key={i}
            char={char}
            index={index}
            totalChars={totalChars}
            progress={scrollYProgress}
          />
        );
      })}
    </p>
  );
}
