"""Draft a week's newsletter with Claude, grounded entirely in the fact pack.

The model is given labelled facts and asked for structured sections that cite
the fact ids they lean on. It is never asked to recall anything about real NFL
players, and never asked to reproduce a table — the site renders those from the
same JSON. Those two decisions remove the failure modes that produced wrong
teams, invented rookies, and mangled scores.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import anthropic
from pydantic import BaseModel, Field
from rich.console import Console

from .config import PROMPTS_DIR, anthropic_api_key, newsletter_path, storylines_path
from .facts import load_facts

console = Console()

MODEL = "claude-opus-5"
MAX_TOKENS = 16000


class Section(BaseModel):
    heading: str = Field(description="Short section heading, no trailing colon.")
    body: str = Field(description="Markdown prose. No tables, no bullet lists of results.")
    fact_ids: list[str] = Field(description="Ids of the FACTS this section draws on.")


class Newsletter(BaseModel):
    title: str = Field(description="Short, specific to this week. No colon-subtitle construction.")
    sections: list[Section]


def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def load_storylines(year: int) -> dict[str, Any]:
    """Running gags, nicknames and rivalries carried week to week.

    Continuity is what separates a league newsletter from generated content, so
    this is hand-curated rather than model-generated.
    """
    path = storylines_path(year)
    if not path.exists():
        seed = {
            "note": "Hand-edited. Callbacks and running jokes the writer should know about.",
            "runningJokes": [],
            "rivalries": [],
            "nicknames": {},
        }
        path.write_text(json.dumps(seed, indent=2) + "\n")
        return seed
    return json.loads(path.read_text())


def _system_blocks(year: int) -> list[dict]:
    """Stable prefix, cached. The volatile fact pack goes in the user turn."""
    storylines = load_storylines(year)
    text = "\n\n".join(
        [
            _prompt("system"),
            _prompt("voice"),
            "## League continuity\n\nRunning jokes, rivalries and nicknames from earlier in the season. "
            "Use them where they land naturally; ignore them where they do not. These are context, "
            "not facts — do not present anything here as something that happened this week.\n\n"
            + json.dumps(storylines, indent=2),
        ]
    )
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _user_message(pack: dict[str, Any]) -> str:
    facts = "\n".join(f"[{f['id']}] {f['text']}" for f in pack["facts"])
    return (
        f"Write the newsletter for week {pack['week']} of the {pack['year']} season "
        f"in {pack['leagueName']}.\n\n"
        f"FACTS\n=====\n{facts}\n"
    )


def generate(year: int, week: int, effort: str = "high") -> Newsletter:
    pack = load_facts(year, week)
    client = anthropic.Anthropic(api_key=anthropic_api_key())

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        output_config={"effort": effort},
        system=_system_blocks(year),
        messages=[{"role": "user", "content": _user_message(pack)}],
        output_format=Newsletter,
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined this request ({response.stop_details}).")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Hit max_tokens before finishing. Raise MAX_TOKENS or lower --effort.")

    usage = response.usage
    console.print(
        f"[dim]{usage.input_tokens} in / {usage.output_tokens} out"
        f" · cache read {getattr(usage, 'cache_read_input_tokens', 0)}[/]"
    )
    return response.parsed_output


def to_markdown(year: int, week: int, letter: Newsletter, pack: dict[str, Any]) -> str:
    """Frontmatter plus prose. status starts as draft; the site only builds published."""
    cited = sorted({fid for s in letter.sections for fid in s.fact_ids})
    front = {
        "title": letter.title,
        "week": week,
        "year": year,
        "date": dt.date.today().isoformat(),
        "status": "draft",
        "model": MODEL,
        "factIds": cited,
    }
    lines = ["---"]
    for key, value in front.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {v}" for v in value)
        elif isinstance(value, str):
            lines.append(f'{key}: "{value}"' if key == "title" else f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---\n")
    for section in letter.sections:
        lines.append(f"## {section.heading}\n")
        lines.append(section.body.strip() + "\n")
    return "\n".join(lines)


def write_newsletter(year: int, week: int, effort: str = "high", run_verify: bool = True, deep: bool = True):
    pack = load_facts(year, week)
    letter = generate(year, week, effort=effort)
    path = newsletter_path(year, week)
    path.write_text(to_markdown(year, week, letter, pack))

    if run_verify:
        from .verify import report

        report(year, week, path.read_text(), deep=deep)
    return path
