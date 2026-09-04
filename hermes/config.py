"""Config loading: profile.yml, llm_config.yml, search_configs.yml.

Examples live in config/*.example.yml. Real configs are gitignored.
Environment variables (GEMINI_API_KEY etc.) override file values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
APPLICATIONS_DIR = DATA_DIR / "applications"


class Identity(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class TargetProfile(BaseModel):
    titles: list[str] = Field(default_factory=list)
    seniority: str = "mid"
    years_experience: int = 0


class Preferences(BaseModel):
    remote_only: bool = False
    min_salary: int = 0
    boards: list[str] = Field(
        default_factory=lambda: ["indeed", "glassdoor", "google"]
    )
    max_results_per_board: int = 40
    max_age_days: int = 14
    blocked_companies: list[str] = Field(default_factory=list)


class Limits(BaseModel):
    max_applications_per_day: int = 20
    min_fit_score: float = 0.65


PROFILE_DIR = CONFIG_DIR / "profiles"


class Profile(BaseModel):
    identity: Identity = Field(default_factory=Identity)
    target: TargetProfile = Field(default_factory=TargetProfile)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    preferences: Preferences = Field(default_factory=Preferences)
    limits: Limits = Field(default_factory=Limits)
    resume_path: str = ""          # per-profile base resume
    search_config_path: str = ""   # per-profile search configs
    name: str = "default"          # profile label

    @property
    def all_skills(self) -> list[str]:
        return [s for group in self.skills.values() for s in group]


class ChainProvider(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    api_base: str = ""


class GenerationSettings(BaseModel):
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout_seconds: int = 60


class RetrySettings(BaseModel):
    attempts: int = 2
    backoff_seconds: int = 5


class LLMConfig(BaseModel):
    chain: list[ChainProvider] = Field(default_factory=list)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    retries: RetrySettings = Field(default_factory=RetrySettings)


class SearchEntry(BaseModel):
    name: str = "default"
    title: str = ""
    location: str = ""
    boards: list[str] = Field(default_factory=list)
    max_results: int = 40
    hours_old: int = 336
    remote_only: bool = False


class SearchConfigs(BaseModel):
    searches: list[SearchEntry] = Field(default_factory=list)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_dotenv(path: Optional[Path] = None) -> None:
    """Minimal .env loader (no python-dotenv dependency).

    Lines of the form KEY=value set os.environ if not already present.
    Handles quotes, comments, and exports. Called by the CLI at startup.
    """
    import os

    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _with_env_chain(cfg: LLMConfig) -> LLMConfig:
    """Inject env keys into chain entries so file values can stay empty."""
    env_map = {
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    for entry in cfg.chain:
        if not entry.api_key:
            env_var = env_map.get(entry.provider)
            if env_var and os.environ.get(env_var):
                entry.api_key = os.environ[env_var]
    return cfg


def load_profile(path: Optional[Path] = None, name: Optional[str] = None) -> Profile:
    """Load a profile by file path, by name from config/profiles/, or default.

    Resolution order: explicit path > named profile > config/profile.yml.
    """
    if path is not None:
        data = _read_yaml(path)
        profile = Profile(**data) if data else Profile()
    elif name is not None and name != "default":
        profile_file = PROFILE_DIR / f"{name}.yml"
        if not profile_file.exists():
            available = (
                [p.stem for p in PROFILE_DIR.glob("*.yml")]
                if PROFILE_DIR.exists()
                else []
            )
            raise FileNotFoundError(
                f"Profile '{name}' not found at {profile_file}. "
                f"Available: {available or 'none'}."
            )
        data = _read_yaml(profile_file)
        profile = Profile(**data) if data else Profile()
        profile.name = name
    else:
        data = _read_yaml(CONFIG_DIR / "profile.yml")
        profile = Profile(**data) if data else Profile()
    if profile.name == "default" and profile.resume_path:
        # Keep the explicit label from the file if set, else fall back.
        profile.name = profile.name
    return profile


def list_profiles() -> list[str]:
    """All available profile names ('default' + profiles dir)."""
    names = ["default"]
    if PROFILE_DIR.exists():
        names.extend(sorted(p.stem for p in PROFILE_DIR.glob("*.yml")))
    return names


def load_llm_config(path: Optional[Path] = None) -> LLMConfig:
    data = _read_yaml(path or CONFIG_DIR / "llm_config.yml")
    cfg = LLMConfig(**data) if data else LLMConfig()
    return _with_env_chain(cfg)


def load_search_configs(
    path: Optional[Path] = None, profile: Optional[Profile] = None
) -> SearchConfigs:
    """Search configs: explicit path > profile-specific > default file."""
    if path is not None:
        data = _read_yaml(path)
        return SearchConfigs(**data) if data else SearchConfigs()
    if profile is not None and profile.search_config_path:
        candidate = Path(profile.search_config_path)
        if not candidate.is_absolute():
            candidate = CONFIG_DIR / candidate.name
        if candidate.exists():
            data = _read_yaml(candidate)
            return SearchConfigs(**data) if data else SearchConfigs()
    data = _read_yaml(CONFIG_DIR / "search_configs.yml")
    return SearchConfigs(**data) if data else SearchConfigs()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
