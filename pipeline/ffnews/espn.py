"""Thin wrapper over espn_api with useful failure messages and per-run caching.

The rest of the pipeline never imports espn_api directly, so if the library's
surface shifts, this is the only file that changes.
"""

from __future__ import annotations

import functools

from espn_api.football import League

from .config import espn_credentials

BENCH_SLOTS = {"BE", "IR"}


class EspnUnavailable(RuntimeError):
    pass


@functools.lru_cache(maxsize=None)
def get_league(year: int) -> League:
    creds = espn_credentials()
    try:
        return League(
            league_id=creds["league_id"],
            year=year,
            swid=creds["swid"],
            espn_s2=creds["espn_s2"],
        )
    except Exception as exc:  # espn_api raises bare Exceptions for auth failures
        raise EspnUnavailable(
            f"Could not load ESPN league {creds['league_id']} for {year}: {exc}\n\n"
            "The usual cause is expired cookies. Log in to fantasy.espn.com, copy fresh\n"
            "SWID and espn_s2 values from DevTools > Application > Cookies, and update .env."
        ) from exc


def box_scores(year: int, week: int):
    league = get_league(year)
    try:
        scores = league.box_scores(week)
    except Exception as exc:
        raise EspnUnavailable(f"box_scores({year}, week {week}) failed: {exc}") from exc
    if not scores:
        raise EspnUnavailable(f"ESPN returned no box scores for {year} week {week}.")
    return scores


TRANSACTION_TYPES = {"FREEAGENT", "WAIVER", "TRADE_ACCEPT"}


def transactions(year: int, week: int) -> tuple[list, bool]:
    """Adds, drops and completed trades processed during a scoring period.

    Returns (transactions, available). ESPN raises both for genuinely quiet
    weeks and for weeks where it returns a malformed record (2025 week 7 hits a
    KeyError on 'status' inside espn_api). Those two cases must not look alike:
    reporting "nobody touched their roster" when the data simply failed to load
    is a false claim, so the caller is told which happened.
    """
    league = get_league(year)
    try:
        return list(league.transactions(scoring_period=week, types=set(TRANSACTION_TYPES)) or []), True
    except Exception:
        return [], False


def power_rankings(year: int, week: int):
    league = get_league(year)
    try:
        return league.power_rankings(week=week) or []
    except Exception:
        return []


def playable_weeks(year: int) -> list[int]:
    """Weeks with at least one recorded score, derived from team schedules."""
    league = get_league(year)
    played = 0
    for team in league.teams:
        scored = [i for i, s in enumerate(team.scores, start=1) if s]
        if scored:
            played = max(played, max(scored))
    return list(range(1, played + 1))
