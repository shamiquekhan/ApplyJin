import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface WordsPullUpProps {
  text: string;
  className?: string;
  showAsterisk?: boolean;
}

/**
 * Splits text by spaces; each word slides up from y:20 with a staggered
 * delay of 0.08s, triggered once when scrolled into view.
 * showAsterisk adds a superscript * after the final "a" of the last word.
 */
export function WordsPullUp({ text, className, showAsterisk = false }: WordsPullUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const words = text.split(" ");

  return (
    <span ref={ref} className={className} style={{ color: "#E1E0CC" }}>
      {words.map((word, i) => {
        const isLast = i === words.length - 1;
        const endsWithA = word.toLowerCase().endsWith("a");
        return (
          <span key={i} className="inline-block overflow-hidden pb-[0.08em] -mb-[0.08em]">
            <motion.span
              className="inline-block"
              initial={{ y: 20, opacity: 0 }}
              animate={inView ? { y: 0, opacity: 1 } : {}}
              transition={{
                duration: 0.6,
                delay: i * 0.08,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              {isLast && showAsterisk && endsWithA ? (
                <span className="relative inline-block">
                  {word.slice(0, -1)}
                  <span className="relative inline-block">a</span>
                  <span className="absolute top-[0.65em] -right-[0.3em] text-[0.31em]">*</span>
                </span>
              ) : (
                word
              )}
              {i < words.length - 1 && "\u00A0"}
            </motion.span>
          </span>
        );
      })}
    </span>
  );
}

interface Segment {
  text: string;
  className?: string;
}

interface WordsPullUpMultiStyleProps {
  segments: Segment[];
  className?: string;
}

/**
 * Takes an array of {text, className} segments, splits all text into
 * individual words (preserving each word's segment className) and applies
 * the same staggered pull-up animation. Words wrapped in inline-flex
 * flex-wrap justify-center.
 */
export function WordsPullUpMultiStyle({ segments, className }: WordsPullUpMultiStyleProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });

  let wordIndex = 0;
  const wordElements = segments.map((segment, segIdx) => {
    const words = segment.text.split(" ");
    return words.map((word, wordIdx) => {
      const delay = wordIndex++ * 0.08;
      return (
        <span
          key={`${segIdx}-${wordIdx}`}
          className="inline-block overflow-hidden pb-[0.1em] -mb-[0.1em]"
        >
          <motion.span
            className={`inline-block ${segment.className || ""}`}
            initial={{ y: 20, opacity: 0 }}
            animate={inView ? { y: 0, opacity: 1 } : {}}
            transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
          >
            {word}
            {wordIdx < words.length - 1 && "\u00A0"}
          </motion.span>
        </span>
      );
    });
  });

  return (
    <span ref={ref} className={`inline-flex flex-wrap justify-center ${className || ""}`}>
      {wordElements}
    </span>
  );
}
