"""LaTeX resume generation (Trey Hunner 'Medium Length Professional CV').

Converts a tailored resume (markdown) into a .tex file using the classic
resume.cls layout, then compiles with pdflatex when available. Also
supports cover letters as simple LaTeX letters.

Everything is escaped — resume content is untrusted text, so no raw TeX
commands can slip through except our own structure.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hermes.latex")

# ---------------------------------------------------------------- resume.cls

_RESUME_CLS = r"""%% resume.cls — Hermes build of the classic Trey Hunner
%% "Medium Length Professional CV" template interface
%% (http://www.treyhunner.com, via LaTeXTemplates.com, MIT licensed).
%% The underlying template is distributed under its own MIT license;
%% this project's code is CC BY-NC 4.0 (see LICENSE).

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/01/01 Hermes resume class]

\LoadClass{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{enumitem}
\usepackage{array}
\pagestyle{empty}
\setlength{\parindent}{0pt}

% Name + address banner (centered header)
\def\name#1{\def\@name{#1}}
\def\address#1{\def\@address{#1}}
\newcommand{\MakeNameHeader}{%
  \begin{center}%
    {\huge\bfseries \@name \par}%
    \vspace{3pt}%
    {\small \@address \par}%
  \end{center}%
  \vspace{-2pt}%
}

% Sections: uppercase bold title with hrule
\newenvironment{rSection}[1]{%
  \vspace{6pt}%
  {\large\bfseries \MakeUppercase{#1}}\vspace{1pt}%
  \hrule\vspace{4pt}%
}{\vspace{4pt}}

% Subsections: bold entry + italic org/dates, compact bullets
\newenvironment{rSubsection}[4]{%
  \vspace{4pt}%
  {\bfseries #1}%
  \ifx\relax#2\relax\else --- {\itshape #2}\fi
  \hfill {\itshape #3}%
  \ifx\relax#4\relax\else \, {\small(#4)}\fi
  \\[1pt]%
  \begin{itemize}[leftmargin=2ex,itemsep=1pt,topsep=1pt,parsep=0pt]%
}{%
  \end{itemize}%
  \vspace{2pt}%
}
"""

# ---------------------------------------------------------------- escaping


def latex_escape(text: str) -> str:
    # Backslash first, via a token so replacement braces aren't re-escaped.
    text = text.replace("\\", "\x00BSLASH\x00")
    replacements = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.replace("\x00BSLASH\x00", r"\textbackslash{}")


def _inline(text: str) -> str:
    """Escape + convert markdown bold/italic/code to LaTeX equivalents."""
    escaped = latex_escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\\1}", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\\textit{\\1}", escaped)
    escaped = re.sub(r"`([^`]+)`", r"\\texttt{\\1}", escaped)
    return escaped


# ---------------------------------------------------------------- parsing

class _Resume:
    def __init__(self) -> None:
        self.name = ""
        self.contact = ""
        self.sections: list[tuple[str, list[str]]] = []  # (title, lines)


def _parse_markdown(md: str) -> _Resume:
    parsed = _Resume()
    current_section: Optional[tuple[str, list[str]]] = None
    lines = md.splitlines()
    i = 0

    # Name + contact: first heading or first non-empty line, then the
    # following non-empty non-heading line is the contact line.
    while i < len(lines):
        line = lines[i].strip()
        if line:
            parsed.name = _strip_md_heading(line)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                nxt = lines[j].strip()
                if not nxt.startswith("#"):
                    parsed.contact = nxt
                    i = j + 1  # consumed name + contact
                else:
                    i = j      # contact absent; next heading is a section
            else:
                i = j
            break
        i += 1

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= 2:
                # ## heading -> new rSection
                title = _strip_md_heading(stripped)
                current_section = (title, [])
                parsed.sections.append(current_section)
            elif current_section is not None:
                # ### heading -> entry header line inside current section
                # (rendered as 'Role | Org | Dates' by rSubsection)
                current_section[1].append(_strip_md_heading(stripped))
        elif current_section is not None:
            current_section[1].append(stripped)
        i += 1

    if not parsed.sections:
        parsed.sections = [("Experience", [l.strip() for l in lines if l.strip()])]
    return parsed


def _strip_md_heading(line: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", line)
    text = re.sub(r"\*+", "", text)
    return text.strip()


# ---------------------------------------------------------------- rendering


def _render_subsection(lines: list[str]) -> str:
    """Render an entry block: 'Role | Company | Dates' + bullets/paras."""
    out: list[str] = []
    header: Optional[tuple[str, str, str]] = None
    bullets: list[str] = []
    paras: list[str] = []

    for line in lines:
        if line.startswith(("- ", "* ", "• ")):
            bullets.append(line[2:].strip())
        else:
            paras.append(line)

    # First paragraph may be a 'Role | Company | Dates' entry header.
    if paras:
        first = paras[0]
        parts = [p.strip() for p in first.split("|")]
        if len(parts) >= 2 and len(parts[0]) < 80:
            role = parts[0]
            org = parts[1] if len(parts) > 1 else ""
            dates = " ".join(parts[2:]) if len(parts) > 2 else ""
            header = (role, org, dates)
            paras = paras[1:]

    if not header and not bullets and not paras:
        return ""  # empty entry — emit nothing (itemize needs \item)

    if header:
        role, org, dates = header
        out.append(
            f"\\begin{{rSubsection}}{{{_inline(role)}}}{{}}"
            f"{{{_inline(org)}}}{{{_inline(dates)}}}"
        )
    else:
        out.append("\\begin{rSubsection}{}{}{}{}")

    for para in paras:
        out.append(f"\\item {_inline(para)}")
    for bullet in bullets:
        out.append(f"\\item {_inline(bullet)}")
    out.append("\\end{rSubsection}")
    return "\n".join(out)


def markdown_to_latex(md: str) -> str:
    """Resume markdown -> .tex document using the resume.cls template."""
    parsed = _parse_markdown(md)

    section_order = [
        ("summary", "Summary"), ("objective", "Objective"),
        ("education", "Education"), ("experience", "Experience"),
        ("projects", "Projects"), ("research", "Research"),
        ("publications", "Publications"), ("skills", "Skills"),
        ("certifications", "Certifications"), ("courses", "Courses"),
        ("achievements", "Achievements"),
    ]

    body: list[str] = []
    for title, lines in parsed.sections:
        lowered = title.lower()
        display = title.upper()

        # Skills-like sections render as a compact tabular, not subsections.
        if any(k in lowered for k in ("skill", "tool", "technolog")):
            body.append(f"\\begin{{rSection}}{{{latex_escape(display)}}}")
            body.append(_render_skills_tabular(lines))
            body.append("\\end{rSection}")
        # Education-like sections render as flat entries with \hfill dates.
        elif "education" in lowered:
            body.append(f"\\begin{{rSection}}{{{latex_escape(display)}}}")
            body.append(_render_flat_entries(lines))
            body.append("\\end{rSection}")
        else:
            body.append(f"\\begin{{rSection}}{{{latex_escape(display)}}}")
            body.append(_render_subsection(lines))
            body.append("\\end{rSection}")

    tex = (
        "\\documentclass{resume}\n"
        "\\usepackage[left=0.4in,top=0.4in,right=0.4in,bottom=0.4in]{geometry}\n"
        "\\begin{document}\n\n"
        f"\\name{{{_inline(parsed.name)}}}\n"
        f"\\address{{{_inline(parsed.contact)}}}\n"
        "\\MakeNameHeader\n\n"
        + "\n".join(body)
        + "\n\n\\end{document}\n"
    )
    return tex


def _render_skills_tabular(lines: list[str]) -> str:
    """'Category: a, b, c' bullets -> bold-label tabular rows."""
    rows: list[tuple[str, str]] = []
    for line in lines:
        content = line.lstrip("-*• ").strip()
        if ":" in content:
            label, _, value = content.partition(":")
            rows.append((label.strip(), value.strip()))
        else:
            rows.append(("", content))
    out = ["\\begin{tabular}{ @{} >{\\bfseries}l @{\\hspace{4ex}} l }"]
    for label, value in rows:
        if label:
            out.append(f"{_inline(label)} & {_inline(value)} \\\\")
        else:
            out.append(f" & {_inline(value)} \\\\")
    out.append("\\end{tabular}")
    return "\n".join(out)


def _render_flat_entries(lines: list[str]) -> str:
    r"""Education entries: 'Degree — School | dates' with \hfill alignment."""
    out: list[str] = []
    for line in lines:
        content = line.lstrip("-*• ").strip()
        if "|" in content:
            left, _, right = content.rpartition("|")
            out.append(f"{{\\bfseries {_inline(left.strip())}}} \\hfill {_inline(right.strip())} \\\\")
        else:
            out.append(f"{_inline(content)} \\\\")
    return "\n".join(out)


# ---------------------------------------------------------------- cover letter


_CLOSING_RE = re.compile(
    r"^(sincerely|best regards|warm regards|kind regards|regards|"
    r"yours(?:\s+(?:truly|sincerely|faithfully))?|respectfully(?:\s+yours)?)\b[,.]?\s*$",
    re.IGNORECASE,
)
_SALUTATION_PREFIXES = ("dear", "to whom", "hello", "hiring", "hi ")


def cover_letter_to_latex(letter_md: str, name: str = "", contact: str = "") -> str:
    """Cover letter -> .tex in the same resume.cls visual style.

    Parses the letter into salutation / body / closing / signature and
    renders with the name banner + hrule aesthetic so the letter matches
    the resume as one application packet:
      [ NAME BANNER / contact / rule ]
      date ...............................................
      Dear ...,
      body paragraphs...
      Sincerely,
      NAME
    """
    paragraphs = [
        re.sub(r"^#+\s*", "", p.strip())
        for p in re.split(r"\n\s*\n", letter_md.strip())
        if p.strip()
    ]

    salutation = ""
    closing = ""
    signature = name
    body: list[str] = []
    in_closing = False

    for para in paragraphs:
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        first_line = lines[0] if lines else ""
        joined = " ".join(lines)
        if in_closing:
            # First short paragraph after the closing = signature line
            if signature == name and joined and len(joined) <= 60:
                signature = joined
            continue
        if not salutation and joined.lower().startswith(_SALUTATION_PREFIXES):
            salutation = first_line
            continue
        if _CLOSING_RE.match(joined.lower()):
            closing = first_line.rstrip(",;:")
            # Signature may be on the next line of the same block
            if len(lines) > 1 and len(lines[1]) <= 60:
                signature = lines[1].strip(" *_")
            in_closing = True
            continue
        body.append(joined)

    if not closing:
        closing = "Sincerely"

    body_tex = "\n\n".join(_inline(p) for p in body)

    salutation_tex = ""
    if salutation:
        salutation_tex = f"{_inline(salutation)}\n" + "\\vspace{8pt}\n\n"

    tex = (
        "\\documentclass{resume}\n"
        "\\usepackage[left=0.75in,top=0.5in,right=0.75in,bottom=0.75in]{geometry}\n"
        "\\begin{document}\n\n"
        f"\\name{{{_inline(name)}}}\n"
        f"\\address{{{_inline(contact)}}}\n"
        "\\MakeNameHeader\n"
        "\\vspace{2pt}\n\\hrule\n\\vspace{16pt}\n\n"
        "\\hfill {\\small\\itshape \\today}\n"
        "\\vspace{14pt}\n\n"
        + salutation_tex
        + body_tex
        + "\n\n\\vspace{12pt}\n\n"
        + f"{_inline(closing)},\n"
        + "\\vspace{28pt}\n\n"
        + f"{{\\bfseries {_inline(signature)}}}\n"
        + "\n\\end{document}\n"
    )
    return tex


# ---------------------------------------------------------------- compilation


def compile_tex(tex_source: str, output_pdf: Path, cls_source: Optional[str] = None) -> Optional[Path]:
    """Compile .tex with pdflatex (2 passes for layout). None on failure.

    Writes resume.cls next to the tex in a temp dir (the template requires
    it in the same directory) and moves the final PDF to output_pdf.
    """
    if shutil.which("pdflatex") is None:
        logger.warning("pdflatex not installed — cannot compile LaTeX")
        return None

    with tempfile.TemporaryDirectory(prefix="hermes_tex_") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "resume.cls").write_text(
            _RESUME_CLS, encoding="utf-8"
        )
        tex_file = tmp_path / "resume.tex"
        tex_file.write_text(tex_source, encoding="utf-8")
        try:
            for _ in range(2):  # 2 passes for stable layout
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                     str(tex_file)],
                    cwd=tmp, capture_output=True, timeout=90,
                    check=True,
                )
            produced = tmp_path / "resume.pdf"
            if not produced.exists():
                return None
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced, output_pdf)
            logger.info("LaTeX PDF compiled: %s", output_pdf)
            return output_pdf
        except subprocess.SubprocessError as exc:
            logger.warning("pdflatex failed: %s", exc)
            return None


def latex_bundle(tex_source: str, bundle_zip: Path) -> Path:
    """Zip the .tex + resume.cls so the user can edit/recompile anywhere."""
    bundle_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("resume.cls", _RESUME_CLS)
        zf.writestr("resume.tex", tex_source)
        zf.writestr(
            "README.txt",
            "Hermes LaTeX bundle\n\n"
            "Compile with:  pdflatex resume.tex   (run twice for stable layout)\n"
            "resume.cls must stay in the same folder as resume.tex.\n",
        )
    return bundle_zip
