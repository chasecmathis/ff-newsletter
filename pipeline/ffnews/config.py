"""Paths and credentials. Everything resolves relative to the repo root."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ffnews/config.py -> ffnews -> pipeline -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CONTENT_DIR = REPO_ROOT / "content" / "newsletters"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

load_dotenv(REPO_ROOT / ".env")


class MissingCredential(RuntimeError):
    """Raised with an actionable message rather than a bare KeyError."""


def _require(name: str, hint: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MissingCredential(f"{name} is not set in {REPO_ROOT / '.env'}.\n{hint}")
    return value


def espn_credentials() -> dict[str, str]:
    hint = (
        "Log in to fantasy.espn.com in a browser, open DevTools > Application > Cookies,\n"
        "and copy the SWID and espn_s2 values. They expire every few months."
    )
    return {
        "league_id": int(_require("ESPN_LEAGUE_ID", hint)),
        "swid": _require("ESPN_SWID", hint),
        "espn_s2": _require("ESPN_S2", hint),
    }


def anthropic_api_key() -> str:
    return _require(
        "ANTHROPIC_API_KEY",
        "Create a key at console.anthropic.com and add it to .env as ANTHROPIC_API_KEY=sk-ant-...",
    )


def season_dir(year: int) -> Path:
    d = DATA_DIR / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d


def week_path(year: int, week: int) -> Path:
    return season_dir(year) / f"week_{week:02d}.json"


def facts_path(year: int, week: int) -> Path:
    return season_dir(year) / f"week_{week:02d}.facts.json"


def league_path(year: int) -> Path:
    return season_dir(year) / "league.json"


def storylines_path(year: int) -> Path:
    return season_dir(year) / "storylines.json"


def newsletter_path(year: int, week: int) -> Path:
    d = CONTENT_DIR / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"week-{week:02d}.md"
