"""ESPN -> committed JSON snapshots.

One file per week holding every rostered player's line, plus that week's
transactions. Snapshots are frozen once written: ESPN can retroactively change
stat corrections, and a newsletter that already shipped should keep matching the
numbers it was written from. Use --force to deliberately re-pull.

Everything is keyed on teamId. Team names change mid-season (2025 saw "Goated"
become "Not so Goated"), so names are stored per-snapshot as historical record.
"""

from __future__ import annotations

import json
from typing import Any

from . import espn
from .config import league_path, week_path
from .espn import BENCH_SLOTS


def _round(value: Any, places: int = 2) -> float:
    try:
        return round(float(value or 0), places)
    except (TypeError, ValueError):
        return 0.0


def _player_line(player) -> dict[str, Any]:
    slot = getattr(player, "slot_position", "FA")
    return {
        "playerId": getattr(player, "playerId", None),
        "name": player.name,
        "position": getattr(player, "position", "UNKNOWN"),
        "slot": slot,
        "started": slot not in BENCH_SLOTS,
        "proTeam": getattr(player, "proTeam", "FA"),
        "proOpponent": getattr(player, "pro_opponent", "None"),
        "points": _round(getattr(player, "points", 0)),
        "projected": _round(getattr(player, "projected_points", 0)),
        "injuryStatus": getattr(player, "injuryStatus", None),
        "onByeWeek": bool(getattr(player, "on_bye_week", False)),
    }


def _side(team, score, lineup) -> dict[str, Any]:
    return {
        "teamId": team.team_id,
        # Historical record: the name this team carried during this week.
        "teamName": team.team_name,
        "score": _round(score),
        "projected": _round(sum(p.projected_points or 0 for p in lineup if p.slot_position not in BENCH_SLOTS)),
        "lineup": [_player_line(p) for p in lineup],
    }


# A third of the raw transaction feed never happened: canceled claims, roster-limit
# failures, and still-pending waivers. Only EXECUTED moves are real.
EXECUTED = "EXECUTED"


def _transaction(txn, player_map: dict) -> dict[str, Any]:
    """espn_api hands back TransactionItem.player as a *name string*, not a Player.

    player_map is bidirectional (id -> name and name -> id), so the reverse
    lookup recovers the id.
    """
    adds, drops = [], []
    for item in txn.items:
        name = item.player if isinstance(item.player, str) else getattr(item.player, "name", "Unknown")
        entry = {"playerId": player_map.get(name), "name": name}
        if item.type == "ADD":
            adds.append(entry)
        elif item.type == "DROP":
            drops.append(entry)
    return {
        "type": txn.type,
        "teamId": txn.team.team_id if txn.team else None,
        "date": txn.date,
        "adds": adds,
        "drops": drops,
    }


def ingest_league(year: int) -> dict[str, Any]:
    """League metadata and the current team roster. Rewritten on every run."""
    league = espn.get_league(year)
    settings = league.settings
    payload = {
        "year": year,
        "name": getattr(settings, "name", f"{year} Season"),
        "teamCount": len(league.teams),
        "regularSeasonWeeks": getattr(settings, "reg_season_count", 14),
        "playoffTeamCount": getattr(settings, "playoff_team_count", 6),
        "teams": [
            {
                "teamId": t.team_id,
                "name": t.team_name,
                "abbrev": t.team_abbrev,
                "owners": [
                    " ".join(filter(None, [o.get("firstName"), o.get("lastName")])).strip()
                    if isinstance(o, dict)
                    else str(o)
                    for o in (t.owners or [])
                ],
                "logo": getattr(t, "logo_url", ""),
                "divisionId": getattr(t, "division_id", 0),
            }
            for t in sorted(league.teams, key=lambda t: t.team_id)
        ],
    }
    path = league_path(year)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def ingest_week(year: int, week: int, force: bool = False) -> dict[str, Any] | None:
    path = week_path(year, week)
    if path.exists() and not force:
        return None

    matchups = []
    for m in espn.box_scores(year, week):
        matchups.append(
            {
                "home": _side(m.home_team, m.home_score, m.home_lineup),
                "away": _side(m.away_team, m.away_score, m.away_lineup),
                "isPlayoff": getattr(m, "is_playoff", False),
            }
        )

    player_map = espn.get_league(year).player_map
    raw_transactions, transactions_available = espn.transactions(year, week)
    payload = {
        "year": year,
        "week": week,
        "matchups": matchups,
        # False means ESPN would not give us the feed — distinct from a quiet week.
        "transactionsAvailable": transactions_available,
        "transactions": [
            _transaction(t, player_map)
            for t in raw_transactions
            if t.status == EXECUTED and t.team is not None
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_week(year: int, week: int) -> dict[str, Any]:
    return json.loads(week_path(year, week).read_text())


def load_league(year: int) -> dict[str, Any]:
    return json.loads(league_path(year).read_text())


def available_weeks(year: int) -> list[int]:
    """Weeks already ingested to disk."""
    from .config import season_dir

    weeks = []
    for p in season_dir(year).glob("week_*.json"):
        if p.name.endswith(".facts.json"):
            continue
        weeks.append(int(p.stem.split("_")[1]))
    return sorted(weeks)
