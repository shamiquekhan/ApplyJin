import { WordsPullUpMultiStyle } from "./WordsPullUp";
import { ScrollRevealText } from "./ScrollRevealText";

export function About() {
  return (
    <section className="bg-black p-4 md:p-6 py-16 md:py-24">
      <div className="bg-[#101010] rounded-2xl md:rounded-[2rem] px-6 py-16 md:py-24 text-center">
        <p className="text-primary text-[10px] sm:text-xs mb-8 md:mb-12">
          Autonomous applications
        </p>

        <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl xl:text-7xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
          <WordsPullUpMultiStyle
            segments={[
              { text: "I am ApplyJin,", className: "font-normal" },
              { text: "a self-taught job agent.", className: "italic font-serif" },
              {
                text: "I have skills in resume tailoring, ATS scoring, and outcome learning.",
                className: "font-normal",
              },
            ]}
          />
        </h2>

        <div className="max-w-3xl mx-auto mt-10 md:mt-16">
          <ScrollRevealText
            className="text-[#DEDBC8] text-sm sm:text-base md:text-lg text-left sm:text-center"
            text="Over the last eight weeks, I have worked with Gemini, LangGraph and a seven-agent pipeline that scouts openings across eight job boards. Together, we have shipped tailored resumes, LaTeX packets and a learning loop that gets sharper with every outcome."
          />
        </div>
      </div>
    </section>
  );
}
