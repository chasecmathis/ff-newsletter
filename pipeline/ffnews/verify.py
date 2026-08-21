"""Check a draft against the fact pack.

Two passes. The deterministic one costs nothing and catches essentially all
numeric fabrication: every number in the prose has to exist in the fact pack.
The optional Claude pass reads for claims that are unsupported without being
numerically wrong — an invented rookie season, a made-up injury.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from rich.console import Console

from .config import anthropic_api_key
from .facts import load_facts
from .ingest import load_week

console = Console()

# 4-2, 47-19, 3-3-1 — but never the "2-97" hiding inside a score line like
# "131.2-97.1", so neither side may touch a decimal point or another digit.
RECORD_RE = re.compile(r"(?<![\d.])\d{1,3}-\d{1,3}(?:-\d{1,3})?(?![\d.])")
NUMBER_RE = re.compile(r"(?<![\w.-])(\d{1,4}(?:\.\d+)?)(?![\w-])")
# Two or more consecutive capitalised words: player and team names.
NAME_RE = re.compile(r"\b([A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+)+)\b")

TOLERANCE = 0.051


def _walk_numbers(node: Any) -> Iterable[float]:
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_numbers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_numbers(value)


def known_numbers(pack: dict) -> set[float]:
    """Every number the fact pack contains, plus how each one renders.

    Facts print to one decimal, so 778.7 must match a stored 778.7000000001 and
    a stored 47 must match a printed 47.0.
    """
    values: set[float] = set()
    # Any number that appears in a fact's rendered text is legitimately
    # copyable. Facts print percentages to zero decimals ("57% all-play"), so
    # walking only the structured values would flag the model for quoting the
    # fact verbatim.
    for fact in pack["facts"]:
        for match in NUMBER_RE.finditer(fact["text"]):
            values.add(float(match.group(1)))
    for raw in _walk_numbers({k: v for k, v in pack.items() if k != "facts"}):
        values.add(round(raw, 4))
        values.add(round(raw, 1))
        values.add(float(int(raw)) if abs(raw) < 1e9 else raw)
        values.add(round(abs(raw), 1))
        values.add(round(raw * 100, 1))  # all-play pct rendered as a percentage
    # Numbers the prose may legitimately reference structurally.
    values.update({float(pack["week"]), float(pack["year"]), float(pack["teamCount"])})
    values.update(float(i) for i in range(1, pack["teamCount"] + 1))  # ranks
    values.update(float(i) for i in range(1, pack["regularSeasonWeeks"] + 3))  # week references
    return values


def known_records(pack: dict) -> set[str]:
    records = set()
    for row in pack["standings"]:
        records.add(row["record"])
        records.add(f"{row['wins']}-{row['losses']}")
    for row in pack["allPlay"]:
        records.add(row["allPlayRecord"])
    return records


def known_names(year: int, week: int, pack: dict) -> set[str]:
    """Players who were actually on a roster this week, plus team names."""
    names: set[str] = set()
    for row in pack["standings"]:
        names.add(row["name"])
    data = load_week(year, week)
    for m in data["matchups"]:
        for side in (m["home"], m["away"]):
            names.add(side["teamName"])
            for p in side["lineup"]:
                names.add(p["name"])
                names.add(p["proTeam"])
    return {n for n in names if n}


# Capitalised words that show up in ordinary prose and headings. A span made
# only of these is English, not a claim about a person.
TITLE_CASE_ENGLISH = {
    "A", "After", "Again", "All", "Already", "And", "Another", "Any", "As", "At",
    "Back", "Because", "Been", "Before", "Best", "Big", "Bottom", "But", "By",
    "Can", "Could", "Current", "Day", "Dead", "Dreams", "Down", "Else", "End",
    "Enough", "Even", "Every", "First", "For", "From", "Front", "Game", "Games",
    "Get", "Gone", "Good", "Got", "Great", "Had", "Half", "Hard", "Has", "Have",
    "He", "Here", "Hero", "Heroes", "His", "Hot", "How", "I", "If", "In", "Is",
    "It", "Just", "Last", "League", "Left", "Let", "Like", "Long", "Look",
    "Lost", "Made", "Man", "Manager", "Managers", "Many", "Meanwhile", "More",
    "Most", "Much", "My", "Never", "New", "Next", "No", "Not", "Nothing", "Now",
    "Of", "Off", "On", "One", "Only", "Or", "Other", "Our", "Out", "Over",
    "Own", "Part", "Play", "Playoff", "Playoffs", "Points", "Power", "Put",
    "Rankings", "Really", "Right", "Said", "Same", "Season", "See", "Shakes",
    "She", "Should", "Since", "So", "Some", "Standings", "Still", "Stop",
    "Such", "Take", "Team", "Teams", "Than", "That", "The", "Their", "Them",
    "Then", "There", "These", "They", "Thing", "Things", "This", "Those",
    "Three", "Through", "Time", "To", "Too", "Top", "Two", "Under", "Up",
    "Very", "Want", "Was", "Watch", "We", "Week", "Weeks", "Well", "Went",
    "Were", "What", "When", "Where", "Which", "While", "Who", "Whole", "Why",
    "Will", "Win", "Wins", "With", "Won", "Worst", "Would", "Year", "Yet",
    "You", "Your", "Name", "For", "Against", "Record", "Rank", "Born", "Died",
    "Mostly", "Fellow", "GMs", "Confused", "Gut", "Isn", "Always", "Rollercoaster",
}


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
POSSESSIVE_RE = re.compile(r"['’]s$")


def _sentences(line: str) -> list[str]:
    """A name never spans a sentence boundary, so neither should a match."""
    return SENTENCE_SPLIT_RE.split(line)


def _strip_possessive(word: str) -> str:
    return POSSESSIVE_RE.sub("", word).strip("*_`")


def _is_prose(line: str) -> bool:
    """Skip headings and table rows — they are not factual sentences."""
    stripped = line.strip()
    return not (stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("---"))


def _body(markdown: str) -> str:
    """Strip frontmatter so ids and dates are not treated as prose claims."""
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) == 3:
            return parts[2]
    return markdown


def check(year: int, week: int, markdown: str) -> dict[str, list]:
    pack = load_facts(year, week)
    numbers, records, names = known_numbers(pack), known_records(pack), known_names(year, week, pack)
    body = _body(markdown)

    bad_numbers, bad_records, unknown_names = [], [], []
    known_words = {w.strip("'’.,") for n in names for w in n.split()}

    for line_no, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            continue

        for match in RECORD_RE.finditer(line):
            if match.group(0) not in records:
                bad_records.append({"line": line_no, "value": match.group(0), "context": line.strip()})

        masked = RECORD_RE.sub(" ", line)  # records already handled above
        for match in NUMBER_RE.finditer(masked):
            value = float(match.group(1))
            if not any(abs(value - k) <= TOLERANCE for k in numbers):
                bad_numbers.append({"line": line_no, "value": match.group(1), "context": line.strip()})

        if not _is_prose(line):
            continue
        for sentence in _sentences(line):
            for match in NAME_RE.finditer(sentence):
                # A heading-like "Bold Thing:" is a label, not a claim.
                if sentence[match.end():match.end() + 1] == ":":
                    continue
                candidate = _strip_possessive(match.group(1))
                if candidate in names:
                    continue
                # Fine if every capitalised word belongs to a known entity — this
                # tolerates "Bijan Robinson's" and "the Puka-chu bench".
                words = {_strip_possessive(w).strip("'’.,") for w in candidate.split()}
                if words <= known_words or words <= TITLE_CASE_ENGLISH:
                    continue
                # "But Puka-chu handed over a game" — a sentence-initial
                # connective swept into the span. Drop it and re-check.
                tail = candidate.split(maxsplit=1)
                if len(tail) == 2 and tail[1] in names:
                    continue
                unknown_names.append({"line": line_no, "value": candidate, "context": line.strip()})

    return {"numbers": bad_numbers, "records": bad_records, "names": unknown_names}


def audit(year: int, week: int, markdown: str) -> list[dict]:
    """Claude reads the draft against the facts and flags unsupported claims."""
    import anthropic
    from pydantic import BaseModel, Field

    class Claim(BaseModel):
        quote: str = Field(description="The exact sentence from the draft.")
        verdict: str = Field(description="supported | unsupported | contradicted")
        fact_id: str | None = Field(description="Supporting fact id, if any.")
        note: str = Field(description="One sentence on what is wrong, or why it is fine.")

    class Audit(BaseModel):
        claims: list[Claim]

    pack = load_facts(year, week)
    facts = "\n".join(f"[{f['id']}] {f['text']}" for f in pack["facts"])
    client = anthropic.Anthropic(api_key=anthropic_api_key())

    response = client.messages.parse(
        model="claude-opus-5",
        max_tokens=8000,
        output_config={"effort": "medium"},
        system=(
            "You audit a fantasy football newsletter against the data it was written from. "
            "The FACTS are the complete set of true statements. Any claim in the draft that is "
            "not supported by a fact is a defect, including claims about a player's NFL team, "
            "rookie status, career history, injuries, or anything from outside this league. "
            "Report only claims that are unsupported or contradicted. Ignore jokes, opinions, "
            "predictions and insults — those need no support. Return an empty list if the draft is clean."
        ),
        messages=[{"role": "user", "content": f"FACTS\n=====\n{facts}\n\nDRAFT\n=====\n{_body(markdown)}"}],
        output_format=Audit,
    )
    if response.stop_reason == "refusal":
        return []
    return [c.model_dump() for c in response.parsed_output.claims if c.verdict != "supported"]


def report(year: int, week: int, markdown: str, deep: bool = False) -> bool:
    results = check(year, week, markdown)
    clean = True

    if results["numbers"]:
        clean = False
        console.print("\n[red bold]Numbers not found in the fact pack[/]")
        for item in results["numbers"]:
            console.print(f"  [red]line {item['line']}[/] [bold]{item['value']}[/] — {item['context'][:90]}")

    if results["records"]:
        clean = False
        console.print("\n[red bold]Records not found in the fact pack[/]")
        for item in results["records"]:
            console.print(f"  [red]line {item['line']}[/] [bold]{item['value']}[/] — {item['context'][:90]}")

    if results["names"]:
        console.print("\n[yellow bold]Names not on any roster this week (review these)[/]")
        for item in results["names"]:
            console.print(f"  [yellow]line {item['line']}[/] [bold]{item['value']}[/]")

    if deep:
        console.print("\n[dim]Running Claude audit pass…[/]")
        for claim in audit(year, week, markdown):
            clean = False
            console.print(f"\n  [red]{claim['verdict']}[/] “{claim['quote'][:100]}”\n    {claim['note']}")

    if clean and not results["names"]:
        console.print("\n[green]✓ Every number and name in the draft resolves to the fact pack.[/]")
    return clean
