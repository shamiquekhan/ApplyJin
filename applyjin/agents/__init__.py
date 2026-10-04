"""ApplyJin agents: one module per pipeline stage."""

from applyjin.agents.cover_letter import CoverLetterAgent
from applyjin.agents.fit_scorer import FitScorer
from applyjin.agents.jd_analyzer import JDAnalyzer
from applyjin.agents.job_scout import scout_jobs
from applyjin.agents.resume_tailor import ResumeTailor
from applyjin.agents.tracker import Tracker

__all__ = [
    "CoverLetterAgent",
    "FitScorer",
    "JDAnalyzer",
    "ResumeTailor",
    "Tracker",
    "scout_jobs",
]
