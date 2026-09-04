"""Master CV Database: the user's complete career record.

One detailed, structured database of everything the user has done —
experiences, projects, education, certifications, skills — with full
detail that never fits on a single resume. Per-job tailored CVs are
SELECTED from this database (top-3 experiences, top-3 projects,
relevant skills), never invented.

Tables (in data/hermes.db alongside the tracker):
    master_profile      — one row: identity + headline + summary
    master_experiences  — roles: title/org/dates/location/desc + bullets
    master_projects     — name/tech/desc + bullets + link
    master_education    — degree/school/dates/details
    master_certifications — name/issuer/year
    master_skills       — category -> skill rows
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes.utils.skill_match import skills_in_text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS master_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    location TEXT DEFAULT '',
    linkedin TEXT DEFAULT '',
    github TEXT DEFAULT '',
    website TEXT DEFAULT '',
    headline TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    years_experience INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS master_experiences (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    organization TEXT DEFAULT '',
    location TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    description TEXT DEFAULT '',
    bullets_json TEXT DEFAULT '[]',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS master_projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    tech TEXT DEFAULT '',
    description TEXT DEFAULT '',
    bullets_json TEXT DEFAULT '[]',
    link TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS master_education (
    id INTEGER PRIMARY KEY,
    degree TEXT NOT NULL,
    institution TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    details TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS master_certifications (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    issuer TEXT DEFAULT '',
    year TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS master_skills (
    id INTEGER PRIMARY KEY,
    category TEXT DEFAULT '',
    name TEXT NOT NULL UNIQUE
);
"""


class MasterStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.execute("INSERT OR IGNORE INTO master_profile (id) VALUES (1)")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------- profile

    def get_profile(self) -> dict:
        row = self.conn.execute("SELECT * FROM master_profile WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def update_profile(self, **fields) -> None:
        allowed = {
            "full_name", "email", "phone", "location", "linkedin",
            "github", "website", "headline", "summary", "years_experience",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return
        sets = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(
            f"UPDATE master_profile SET {sets}, updated_at = ? WHERE id = 1",
            (*updates.values(), datetime.utcnow()),
        )
        self.conn.commit()

    # ---------------------------------------------------------- experiences

    def add_experience(
        self, title: str, organization: str = "", location: str = "",
        start_date: str = "", end_date: str = "", description: str = "",
        bullets: Optional[list[str]] = None, tags: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO master_experiences "
            "(title, organization, location, start_date, end_date, description, bullets_json, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, organization, location, start_date, end_date, description,
             json.dumps(bullets or []), tags),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_experiences(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM master_experiences ORDER BY id"
        ).fetchall()
        return [_exp_row(r) for r in rows]

    def delete_experience(self, exp_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM master_experiences WHERE id = ?", (exp_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------- projects

    def add_project(
        self, name: str, tech: str = "", description: str = "",
        bullets: Optional[list[str]] = None, link: str = "", tags: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO master_projects "
            "(name, tech, description, bullets_json, link, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, tech, description, json.dumps(bullets or []), link, tags),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_projects(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM master_projects ORDER BY id").fetchall()
        return [_proj_row(r) for r in rows]

    def delete_project(self, project_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM master_projects WHERE id = ?", (project_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------- education / certs

    def add_education(
        self, degree: str, institution: str = "",
        start_date: str = "", end_date: str = "", details: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO master_education (degree, institution, start_date, end_date, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (degree, institution, start_date, end_date, details),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_education(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM master_education ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def add_certification(self, name: str, issuer: str = "", year: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO master_certifications (name, issuer, year) VALUES (?, ?, ?)",
            (name, issuer, year),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_certifications(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM master_certifications ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------- skills

    def add_skills(self, category: str, names: list[str]) -> int:
        added = 0
        for name in names:
            try:
                self.conn.execute(
                    "INSERT INTO master_skills (category, name) VALUES (?, ?)",
                    (category, name),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # unique
        self.conn.commit()
        return added

    def list_skills(self) -> dict[str, list[str]]:
        rows = self.conn.execute(
            "SELECT category, name FROM master_skills ORDER BY category, name"
        ).fetchall()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r["category"] or "other", []).append(r["name"])
        return out

    def all_skill_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM master_skills").fetchall()
        return [r["name"] for r in rows]

    def delete_skill(self, name: str) -> bool:
        cur = self.conn.execute("DELETE FROM master_skills WHERE name = ?", (name,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------- snapshot

    def snapshot(self) -> dict:
        """The whole master DB as one dict (used by the tailor)."""
        return {
            "profile": self.get_profile(),
            "experiences": self.list_experiences(),
            "projects": self.list_projects(),
            "education": self.list_education(),
            "certifications": self.list_certifications(),
            "skills": self.list_skills(),
        }

    def stats(self) -> dict:
        return {
            "experiences": len(self.list_experiences()),
            "projects": len(self.list_projects()),
            "education": len(self.list_education()),
            "certifications": len(self.list_certifications()),
            "skills": len(self.all_skill_names()),
            "profile_complete": bool(self.get_profile().get("full_name")),
        }


def _exp_row(row) -> dict:
    data = dict(row)
    data["bullets"] = json.loads(data.pop("bullets_json") or "[]")
    return data


def _proj_row(row) -> dict:
    data = dict(row)
    data["bullets"] = json.loads(data.pop("bullets_json") or "[]")
    return data


# ---------------------------------------------------------------- import


def import_from_resume_text(text: str, store: MasterStore) -> dict:
    """Populate the master DB from a markdown resume (base or tailored).

    Parses the established section conventions (## Experience with ###
    entries + bullets, ## Projects, ## Education, ## Relevant Skills)
    and fills profile fields from the header. Idempotent-ish: duplicate
    skills are skipped; entries are appended each run — import once.
    """
    import re

    lines = text.splitlines()
    imported = {
        "profile": 0, "experiences": 0, "projects": 0,
        "education": 0, "skills": 0,
    }

    # ---- header -> profile
    non_empty = [l.strip() for l in lines if l.strip()]
    if non_empty:
        name = re.sub(r"^[#*\s]+", "", non_empty[0]).strip()
        if 2 < len(name) <= 60 and not any(c.isdigit() for c in name):
            store.update_profile(full_name=name)
            imported["profile"] += 1
        if len(non_empty) > 1:
            contact = non_empty[1]
            email_m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", contact)
            if email_m:
                store.update_profile(email=email_m.group(0))
                imported["profile"] += 1
            linkedin_m = re.search(r"(linkedin\.com/[^\s|]+)", contact)
            if linkedin_m:
                store.update_profile(linkedin=linkedin_m.group(1))
                imported["profile"] += 1
            github_m = re.search(r"(github\.com/[^\s|]+)", contact)
            if github_m:
                store.update_profile(github=github_m.group(1))
                imported["profile"] += 1
            location_guess = contact.split("|")[0].strip().rstrip(",")
            if location_guess and not email_m or ("|" in contact):
                store.update_profile(location=location_guess)

    # ---- sections
    section = ""
    entry: Optional[dict] = None
    section_re = re.compile(r"^##\s+(.*)$")
    entry_re = re.compile(r"^###\s+(.*)$")
    bullet_re = re.compile(r"^[-*•]\s+(.*)$")
    skill_line_re = re.compile(r"^[-*•]\s+([A-Za-z][\w&/ ()+-]*?):\s+(.*)$")

    # Docx/plain-text resumes use ALL-CAPS section headers ("EXPERIENCE").
    caps_section_re = re.compile(r"^(EXPERIENCE|EMPLOYMENT|WORK EXPERIENCE|"
                                 r"PROJECTS?|RELEVANT SKILLS?|SKILLS?|TECHNICAL SKILLS?|"
                                 r"EDUCATION|CERTIFICATIONS?|PUBLICATIONS|"
                                 r"RESEARCH(?: & PUBLICATIONS)?|SUMMARY|"
                                 r"PROFESSIONAL SUMMARY)\s*$")

    def classify(title: str) -> str:
        t = title.strip().lower()
        if "experience" in t or "employment" in t or t.startswith("work"):
            return "experience"
        if "project" in t:
            return "projects"
        if "education" in t:
            return "education"
        if "skill" in t or "technolog" in t or t == "tools":
            return "skills"
        if "certification" in t:
            return "certifications"
        return ""

    def flush_entry(store, entry, section) -> None:
        if not entry:
            return
        if section == "experience":
            store.add_experience(**entry)
            imported["experiences"] += 1
        elif section == "projects":
            store.add_project(**entry)
            imported["projects"] += 1

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        sec_m = section_re.match(stripped)
        caps_m = caps_section_re.match(stripped)
        ent_m = entry_re.match(stripped)
        bul_m = bullet_re.match(stripped)

        # Markdown heading OR ALL-CAPS plain-text header switches section.
        if sec_m or caps_m:
            flush_entry(store, entry, section)
            entry = None
            title = sec_m.group(1) if sec_m else caps_m.group(1)
            section = classify(title)
            continue

        # Plain-text role header detection:
        #   experience: "AI Engineer Intern  |  Suproc  Jul 2026 – Present"
        #              (pipe-separated with dates, or "Role | Org" pairs)
        #   projects:   "RoadSense — Python, GPS probe data" (dash title)
        #              or "Name | tech" pipes with no dates
        if (
            section in ("experience", "projects")
            and not ent_m
            and not bul_m
            and stripped
            and len(stripped) < 160
        ):
            has_dates = bool(re.search(r"\b(?:19|20)\d{2}\b|Present", stripped))
            pipe_parts = [p.strip() for p in re.split(r"\s*\|\s*", stripped) if p.strip()]
            is_header = False
            if section == "experience":
                # pipes + (dates anywhere, or >=2 parts with the last part
                # containing a date/Present)
                is_header = len(pipe_parts) >= 2 and (
                    has_dates or len(pipe_parts) >= 3
                )
            else:
                # project: pipes OR an em/en-dash title line followed by bullets
                dash = bool(re.search(r"\s[—–-]\s", stripped))
                is_header = (len(pipe_parts) >= 1 and (has_dates or dash or len(pipe_parts) >= 2)) and (
                    not re.match(r"^[A-Z][a-z]+ [a-z]", stripped) or True
                )
                # avoid treating descriptive sentences as titles
                if len(stripped) > 140 or stripped.count(" ") > 14:
                    is_header = False
            if is_header:
                flush_entry(store, entry, section)
                if section == "experience":
                    # Segments like "Suproc\tJul 2026 – Present | Remote"
                    # hide dates inside the org part — split on tab too.
                    org_raw = pipe_parts[1] if len(pipe_parts) > 1 else ""
                    org_bits = [b.strip() for b in re.split(r"[\t|]", org_raw) if b.strip()]
                    org = org_bits[0] if org_bits else ""
                    # Dates may be embedded in any segment after the org.
                    date_text = " ".join(org_bits[1:])
                    rest = " ".join(pipe_parts[2:]) if len(pipe_parts) > 2 else ""
                    all_dates = f"{date_text} {rest}"
                    # Keep location as part of the description context
                    loc = next(
                        (b for b in org_bits[1:] + pipe_parts[2:]
                         if not re.search(r"(?:19|20)\d{2}|Present", b)),
                        "",
                    )
                    date_bits = [
                        d for d in re.split(r"\s*[–-]\s*", all_dates)
                        if re.search(r"(?:19|20)\d{2}|Present", d)
                    ]
                    entry = {
                        "title": pipe_parts[0].split("\t")[0].strip(),
                        "organization": org,
                        "location": loc,
                        "start_date": date_bits[0] if date_bits else "",
                        "end_date": date_bits[1] if len(date_bits) > 1 else ("Present" if "Present" in all_dates else ""),
                        "bullets": [],
                    }
                else:
                    first = pipe_parts[0]
                    # "RoadSense — Python, GPS" -> name + tech
                    if re.search(r"\s[—–]\s", first):
                        name_seg, _, tech_seg = re.split(r"(\s[—–]\s)", first, maxsplit=1)
                        name, tech = name_seg.strip(), tech_seg.strip()
                    else:
                        name, tech = first, ""
                    entry = {
                        "name": name,
                        "tech": tech or (" ".join(pipe_parts[1:]) if len(pipe_parts) > 1 else ""),
                        "bullets": [],
                    }
                continue

        if ent_m and section in ("experience", "projects", "education"):
            flush_entry(store, entry, section)
            header = [p.strip() for p in ent_m.group(1).split("|")]
            if section == "experience":
                entry = {
                    "title": header[0] if header else "",
                    "organization": header[1] if len(header) > 1 else "",
                    "start_date": header[2].split("–")[0].strip() if len(header) > 2 else "",
                    "end_date": header[2].split("–")[-1].strip() if len(header) > 2 else "",
                    "bullets": [],
                }
            elif section == "projects":
                entry = {
                    "name": header[0] if header else "",
                    "tech": ", ".join(header[1:]) if len(header) > 1 else "",
                    "bullets": [],
                }
            else:
                store.add_education(
                    degree=header[0] if header else "",
                    institution=header[1] if len(header) > 1 else "",
                    end_date=header[2] if len(header) > 2 else "",
                )
                imported["education"] += 1
                entry = None
            continue
        if bul_m:
            content = bul_m.group(1).strip()
            if section == "skills":
                skill_m = skill_line_re.match(stripped)
                if skill_m:
                    category = skill_m.group(1).strip().lower()
                    names = [n.strip() for n in re.split(r",", skill_m.group(2)) if n.strip()]
                    imported["skills"] += store.add_skills(category, names)
                else:
                    imported["skills"] += store.add_skills(
                        "other", [n.strip() for n in content.split(",") if n.strip()]
                    )
            elif section == "education":
                # "- Degree | Institution | dates" or plain line
                parts = [p.strip() for p in content.split("|")]
                store.add_education(
                    degree=parts[0] if parts else content,
                    institution=parts[1] if len(parts) > 1 else "",
                    end_date=" ".join(parts[2:]) if len(parts) > 2 else "",
                )
                imported["education"] += 1
            elif section == "certifications":
                for cert in content.split("·"):
                    cert = cert.strip()
                    if cert:
                        store.add_certification(name=cert)
            elif entry is not None:
                entry["bullets"].append(content)
        elif section == "certifications" and stripped and not stripped.startswith("#"):
            for cert in stripped.split("·"):
                cert = cert.strip()
                if cert:
                    store.add_certification(name=cert)

    flush_entry(store, entry, section)
    return imported
