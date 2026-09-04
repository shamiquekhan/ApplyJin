import { useRef } from "react";
import { motion, useScroll, useTransform, MotionValue } from "framer-motion";

interface AnimatedLetterProps {
  char: string;
  index: number;
  totalChars: number;
  progress: MotionValue<number>;
}

/** One character whose opacity (0.2 -> 1) follows the section scroll. */
function AnimatedLetter({ char, index, totalChars, progress }: AnimatedLetterProps) {
  const charProgress = index / totalChars;
  const opacity = useTransform(
    progress,
    [charProgress - 0.1, charProgress + 0.05],
    [0.2, 1]
  );
  if (char === " ") {
    // Word separator: a plain space (breakable), styled like its neighbors.
    return <motion.span style={{ opacity }}>{" "}</motion.span>;
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
 * Layout-safe: text is split into words first (each an inline-block span),
 * so line wrapping stays natural. Rendering every space as \u00A0 — the
 * naive per-char approach — turns the whole paragraph into one unbreakable
 * "word" and overflows the page horizontally.
 */
export function ScrollRevealText({ text, className }: ScrollRevealTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.8", "end 0.2"],
  });

  const words = text.split(" ");
  let charCount = 0;
  const totalChars = text.length;

  return (
    <p
      ref={ref}
      className={className}
      style={{ maxWidth: "100%", overflowWrap: "break-word" }}
    >
      {words.map((word, w) => (
        <span key={w} className="inline-block whitespace-nowrap">
          {word.split("").map((char, i) => {
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
          {w < words.length - 1 && (
            <AnimatedLetter
              char=" "
              index={charCount++}
              totalChars={totalChars}
              progress={scrollYProgress}
            />
          )}
        </span>
      ))}
    </p>
  );
}
