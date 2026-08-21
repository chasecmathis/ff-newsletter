"""All derivation happens here, exactly once.

The site renders from this file and the newsletter prompt is built from this
file, so the prose can never contradict the tables: neither of them computed
anything.

Every fact carries a stable id so the drafting model can cite it and the
verifier can check it.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .config import facts_path
from .ingest import available_weeks, load_league, load_week

# QB 1 / RB 2 / WR 2 / TE 1 / FLEX 1 / D-ST 1 / K 1
STARTING_SLOTS: dict[str, int] = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "D/ST": 1, "K": 1}
FLEX_SLOT = "RB/WR/TE"
FLEX_POSITIONS = {"RB", "WR", "TE"}
SCORING_POSITIONS = ["QB", "RB", "WR", "TE", "D/ST", "K"]


def _fmt(value: float) -> str:
    """One decimal place, the way a scoreboard shows it."""
    return f"{value:.1f}"


def _sides(week_data: dict) -> Iterable[dict]:
    for m in week_data["matchups"]:
        yield m["away"]
        yield m["home"]


def regular_season_weeks(year: int, through: int | None = None) -> list[int]:
    """Weeks that are actually single-week matchups.

    This league's playoffs run as one matchup across weeks 14-15, and ESPN
    reports the same cumulative two-week total under both scoring periods. Those
    totals are roughly double a normal week, so folding them into standings,
    all-play or season records would corrupt every one of them.
    """
    limit = load_league(year)["regularSeasonWeeks"]
    weeks = [w for w in available_weeks(year) if w <= limit]
    return [w for w in weeks if through is None or w <= through]


def is_playoff_week(year: int, week: int) -> bool:
    return week > load_league(year)["regularSeasonWeeks"]


# ---------------------------------------------------------------- lineups


def optimal_lineup(lineup: list[dict]) -> tuple[float, list[dict]]:
    """Best legal starting lineup from the players who were actually rosterable.

    IR players are excluded: they were locked and could not have been started,
    so counting them would produce a "you should have started him" claim that
    isn't true.

    With one flex and position-exclusive dedicated slots, greedy is exactly
    optimal: fill each dedicated slot with the best at that position, then give
    the flex to the best remaining flex-eligible player.
    """
    available = [p for p in lineup if p["slot"] != "IR"]
    by_position: dict[str, list[dict]] = {}
    for p in available:
        by_position.setdefault(p["position"], []).append(p)
    for players in by_position.values():
        players.sort(key=lambda p: p["points"], reverse=True)

    chosen: list[dict] = []
    used: set[int] = set()
    for position, count in STARTING_SLOTS.items():
        for p in by_position.get(position, [])[:count]:
            chosen.append({**p, "optimalSlot": position})
            used.add(id(p))

    flex_pool = [p for p in available if p["position"] in FLEX_POSITIONS and id(p) not in used]
    if flex_pool:
        best_flex = max(flex_pool, key=lambda p: p["points"])
        chosen.append({**best_flex, "optimalSlot": FLEX_SLOT})

    return round(sum(p["points"] for p in chosen), 2), chosen


def worst_decision(lineup: list[dict]) -> dict | None:
    """The single start/sit call that cost the most points.

    Compares the lowest-scoring starter against the highest-scoring bench player
    who could legally have filled that same slot.
    """
    starters = [p for p in lineup if p["started"]]
    bench = [p for p in lineup if not p["started"] and p["slot"] != "IR"]
    if not starters or not bench:
        return None

    best: dict | None = None
    for started in starters:
        slot = started["slot"]
        eligible = FLEX_POSITIONS if slot == FLEX_SLOT else {slot}
        for benched in bench:
            if benched["position"] not in eligible:
                continue
            lost = round(benched["points"] - started["points"], 2)
            if lost > 0 and (best is None or lost > best["pointsLost"]):
                best = {
                    "slot": slot,
                    "startedName": started["name"],
                    "startedPoints": started["points"],
                    "benchedName": benched["name"],
                    "benchedPoints": benched["points"],
                    "pointsLost": lost,
                }
    return best


# ---------------------------------------------------------------- season state


def _team_names(year: int, through_week: int) -> dict[int, str]:
    """Most recent name each team carried, up to and including this week."""
    names: dict[int, str] = {}
    for w in (w for w in available_weeks(year) if w <= through_week):
        for side in _sides(load_week(year, w)):
            names[side["teamId"]] = side["teamName"]
    return names


def standings_through(year: int, week: int) -> list[dict]:
    records: dict[int, dict] = {}
    for w in regular_season_weeks(year, week):
        for m in load_week(year, w)["matchups"]:
            home, away = m["home"], m["away"]
            for side, opponent in ((home, away), (away, home)):
                r = records.setdefault(
                    side["teamId"],
                    {"teamId": side["teamId"], "wins": 0, "losses": 0, "ties": 0,
                     "pointsFor": 0.0, "pointsAgainst": 0.0, "results": []},
                )
                r["pointsFor"] += side["score"]
                r["pointsAgainst"] += opponent["score"]
                if side["score"] > opponent["score"]:
                    r["wins"] += 1
                    r["results"].append("W")
                elif side["score"] < opponent["score"]:
                    r["losses"] += 1
                    r["results"].append("L")
                else:
                    r["ties"] += 1
                    r["results"].append("T")

    names = _team_names(year, week)
    table = []
    for r in records.values():
        streak_type = r["results"][-1] if r["results"] else ""
        streak = 0
        for result in reversed(r["results"]):
            if result != streak_type:
                break
            streak += 1
        table.append(
            {
                **{k: v for k, v in r.items() if k != "results"},
                "name": names.get(r["teamId"], f"Team {r['teamId']}"),
                "pointsFor": round(r["pointsFor"], 2),
                "pointsAgainst": round(r["pointsAgainst"], 2),
                "streak": f"{streak_type}{streak}" if streak else "-",
                "record": f"{r['wins']}-{r['losses']}" + (f"-{r['ties']}" if r["ties"] else ""),
            }
        )

    table.sort(key=lambda t: (-t["wins"], -t["pointsFor"]))
    for rank, row in enumerate(table, start=1):
        row["rank"] = rank
    return table


def all_play_through(year: int, week: int) -> list[dict]:
    """Record if every team had played every other team every week.

    This replaces ESPN's opaque power score. It is the standard fantasy measure
    of true strength, it is reproducible from committed snapshots, and unlike a
    "power score of 28.20" it means something to a reader.
    """
    tally: dict[int, dict] = {}
    for w in regular_season_weeks(year, week):
        scores = [(s["teamId"], s["score"]) for s in _sides(load_week(year, w))]
        for team_id, score in scores:
            t = tally.setdefault(team_id, {"teamId": team_id, "allPlayWins": 0, "allPlayLosses": 0, "allPlayTies": 0})
            for other_id, other_score in scores:
                if other_id == team_id:
                    continue
                if score > other_score:
                    t["allPlayWins"] += 1
                elif score < other_score:
                    t["allPlayLosses"] += 1
                else:
                    t["allPlayTies"] += 1

    actual = {row["teamId"]: row for row in standings_through(year, week)}
    names = _team_names(year, week)
    rows = []
    for t in tally.values():
        games = t["allPlayWins"] + t["allPlayLosses"] + t["allPlayTies"]
        pct = t["allPlayWins"] / games if games else 0.0
        real = actual.get(t["teamId"], {})
        played = (real.get("wins", 0) + real.get("losses", 0) + real.get("ties", 0)) or 1
        rows.append(
            {
                **t,
                "name": names.get(t["teamId"], f"Team {t['teamId']}"),
                "allPlayRecord": f"{t['allPlayWins']}-{t['allPlayLosses']}",
                "allPlayPct": round(pct, 4),
                # Positive = winning more than the scores deserve.
                "luck": round(real.get("wins", 0) - pct * played, 2),
            }
        )
    rows.sort(key=lambda r: -r["allPlayPct"])
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


# ---------------------------------------------------------------- week detail


def week_detail(year: int, week: int) -> dict[str, Any]:
    data = load_week(year, week)
    matchups, efficiency = [], []

    for m in data["matchups"]:
        home, away = m["home"], m["away"]
        winner, loser = (home, away) if home["score"] >= away["score"] else (away, home)
        matchups.append(
            {
                "winnerTeamId": winner["teamId"],
                "winnerName": winner["teamName"],
                "winnerScore": winner["score"],
                "loserTeamId": loser["teamId"],
                "loserName": loser["teamName"],
                "loserScore": loser["score"],
                "margin": round(winner["score"] - loser["score"], 2),
                "isTie": home["score"] == away["score"],
            }
        )
        for side in (home, away):
            optimal, _ = optimal_lineup(side["lineup"])
            efficiency.append(
                {
                    "teamId": side["teamId"],
                    "name": side["teamName"],
                    "actual": side["score"],
                    "optimal": optimal,
                    "pointsLeftOnBench": round(optimal - side["score"], 2),
                    "efficiencyPct": round(100 * side["score"] / optimal, 1) if optimal else 0.0,
                    "worstDecision": worst_decision(side["lineup"]),
                }
            )

    efficiency.sort(key=lambda e: -e["pointsLeftOnBench"])
    team_scores = sorted(
        ({"teamId": s["teamId"], "name": s["teamName"], "score": s["score"]} for s in _sides(data)),
        key=lambda s: -s["score"],
    )

    return {
        "matchups": matchups,
        "efficiency": efficiency,
        "teamScores": team_scores,
        "highestTeam": team_scores[0],
        "lowestTeam": team_scores[-1],
        "closestGame": min(matchups, key=lambda x: x["margin"]),
        "biggestBlowout": max(matchups, key=lambda x: x["margin"]),
        "positionLeaders": position_leaders(data),
        "projections": projection_extremes(data),
        # Older snapshots predate the flag; absent means the feed was fine.
        "transactionsAvailable": data.get("transactionsAvailable", True),
        "transactions": transaction_summary(data),
    }


def position_leaders(data: dict) -> dict[str, dict]:
    """Best and worst started, plus the best player left on a bench."""
    leaders: dict[str, dict] = {}
    for position in SCORING_POSITIONS:
        started, benched = [], []
        for side in _sides(data):
            for p in side["lineup"]:
                if p["position"] != position:
                    continue
                entry = {**p, "teamId": side["teamId"], "teamName": side["teamName"]}
                if p["started"]:
                    started.append(entry)
                elif p["slot"] != "IR" and not p["onByeWeek"]:
                    benched.append(entry)
        if not started:
            continue
        leaders[position] = {
            "bestStarted": max(started, key=lambda p: p["points"]),
            "worstStarted": min(started, key=lambda p: p["points"]),
            "bestBenched": max(benched, key=lambda p: p["points"]) if benched else None,
        }
    return leaders


def projection_extremes(data: dict) -> dict[str, Any]:
    """Started players who most beat or missed their projection.

    Requires a real projection: a zero projection means ESPN never set one.
    """
    lines = []
    for side in _sides(data):
        for p in side["lineup"]:
            if p["started"] and p["projected"] > 0:
                lines.append(
                    {**p, "teamId": side["teamId"], "teamName": side["teamName"],
                     "delta": round(p["points"] - p["projected"], 2)}
                )
    if not lines:
        return {"biggestBoom": None, "biggestBust": None}
    return {
        "biggestBoom": max(lines, key=lambda p: p["delta"]),
        "biggestBust": min(lines, key=lambda p: p["delta"]),
    }


def transaction_summary(data: dict) -> list[dict]:
    names = {s["teamId"]: s["teamName"] for s in _sides(data)}
    return [
        {**t, "teamName": names.get(t["teamId"], f"Team {t['teamId']}")}
        for t in data.get("transactions", [])
    ]


# ---------------------------------------------------------------- fact pack


def _sentences(year: int, week: int, standings, allplay, detail) -> list[dict]:
    """Flatten everything into labelled statements.

    This list is the model's entire world: the system prompt tells it these are
    the only true statements it has, and every number it writes must come from
    here. Ids are stable so a draft can cite them and the verifier can resolve
    them.
    """
    facts: list[dict] = []

    def add(fact_id: str, text: str) -> None:
        facts.append({"id": fact_id, "text": text})

    # League shape belongs in the facts, not in prose around them: the writer
    # cites it and the verifier can resolve it.
    league = load_league(year)
    played = len(regular_season_weeks(year, week))
    remaining = max(0, league["regularSeasonWeeks"] - played)
    add(
        "league.format",
        f"{league['teamCount']} teams. {league['playoffTeamCount']} make the playoffs. "
        f"The regular season is {league['regularSeasonWeeks']} weeks.",
    )
    add(
        "league.remaining",
        f"This is week {week}. {remaining} regular season week{'' if remaining == 1 else 's'} "
        f"remain after it." if remaining else
        f"This is week {week}, the final week of the regular season.",
    )

    scoring_rank = {
        row["teamId"]: i
        for i, row in enumerate(sorted(standings, key=lambda r: -r["pointsFor"]), start=1)
    }
    for row in standings:
        add(
            f"standings.{row['rank']}",
            f"{row['name']} is {row['rank']} of {len(standings)} at {row['record']} "
            f"with {_fmt(row['pointsFor'])} points for and {_fmt(row['pointsAgainst'])} against "
            f"(current streak {row['streak']}). They rank {scoring_rank[row['teamId']]} "
            f"of {len(standings)} in points scored.",
        )

    for row in allplay:
        luck = row["luck"]
        if abs(luck) < 0.75:
            verdict = "Their record is about what their scoring earned."
        elif luck < 0:
            verdict = (f"Their record is {abs(luck):.2f} wins WORSE than their scoring earned — "
                       f"they have been unlucky.")
        else:
            verdict = (f"Their record is {luck:.2f} wins BETTER than their scoring earned — "
                       f"they have been lucky.")
        add(
            f"allplay.{row['rank']}",
            f"{row['name']} is {row['allPlayRecord']} against the entire league "
            f"({row['allPlayPct'] * 100:.0f}% all-play win rate), ranking {row['rank']} in true strength. "
            f"{verdict}",
        )

    for i, m in enumerate(detail["matchups"], start=1):
        verb = "tied" if m["isTie"] else "beat"
        add(
            f"matchup.{i}",
            f"{m['winnerName']} {verb} {m['loserName']} {_fmt(m['winnerScore'])} to "
            f"{_fmt(m['loserScore'])}, a margin of {_fmt(m['margin'])}.",
        )

    add("week.highest", f"{detail['highestTeam']['name']} was the week's highest scorer with {_fmt(detail['highestTeam']['score'])}.")
    add("week.lowest", f"{detail['lowestTeam']['name']} was the week's lowest scorer with {_fmt(detail['lowestTeam']['score'])}.")
    closest, blowout = detail["closestGame"], detail["biggestBlowout"]
    add("week.closest", f"The closest game was {closest['winnerName']} over {closest['loserName']} by {_fmt(closest['margin'])}.")
    add("week.blowout", f"The largest margin was {blowout['winnerName']} over {blowout['loserName']} by {_fmt(blowout['margin'])}.")

    for position, group in detail["positionLeaders"].items():
        best = group["bestStarted"]
        add(
            f"position.best.{position}",
            f"The top scoring started {position} was {best['name']} ({best['proTeam']} vs {best['proOpponent']}) "
            f"with {_fmt(best['points'])} for {best['teamName']}.",
        )
        worst = group["worstStarted"]
        add(
            f"position.worst.{position}",
            f"The lowest scoring started {position} was {worst['name']} ({worst['proTeam']}) "
            f"with {_fmt(worst['points'])} for {worst['teamName']}.",
        )
        if group["bestBenched"]:
            benched = group["bestBenched"]
            add(
                f"position.benched.{position}",
                f"The best {position} left on a bench was {benched['name']} ({benched['proTeam']}) "
                f"with {_fmt(benched['points'])}, benched by {benched['teamName']}.",
            )

    for i, e in enumerate(detail["efficiency"][:4], start=1):
        add(
            f"bench.wasted.{i}",
            f"{e['name']} scored {_fmt(e['actual'])} of a possible {_fmt(e['optimal'])} "
            f"({e['efficiencyPct']}% lineup efficiency), leaving {_fmt(e['pointsLeftOnBench'])} on the bench.",
        )
        d = e["worstDecision"]
        if d and i <= 2:
            add(
                f"bench.decision.{i}",
                f"{e['name']} started {d['startedName']} ({_fmt(d['startedPoints'])}) over "
                f"{d['benchedName']} ({_fmt(d['benchedPoints'])}) at {d['slot']}, costing {_fmt(d['pointsLost'])}.",
            )

    best_eff = min(detail["efficiency"], key=lambda e: e["pointsLeftOnBench"])
    add(
        "bench.best",
        f"{best_eff['name']} managed the cleanest lineup at {best_eff['efficiencyPct']}% efficiency, "
        f"leaving only {_fmt(best_eff['pointsLeftOnBench'])} on the bench.",
    )

    boom, bust = detail["projections"]["biggestBoom"], detail["projections"]["biggestBust"]
    if boom:
        add(
            "projection.boom",
            f"{boom['name']} ({boom['teamName']}) beat his {_fmt(boom['projected'])} projection by "
            f"{_fmt(boom['delta'])}, scoring {_fmt(boom['points'])}.",
        )
    if bust:
        add(
            "projection.bust",
            f"{bust['name']} ({bust['teamName']}) missed his {_fmt(bust['projected'])} projection by "
            f"{_fmt(abs(bust['delta']))}, scoring only {_fmt(bust['points'])}.",
        )

    if not detail["transactionsAvailable"]:
        add(
            "transaction.unavailable",
            "ESPN did not return the roster-move feed for this week, so no waiver, "
            "free-agent or trade activity is known. Do not say it was a quiet week — "
            "the data is missing, not empty.",
        )

    for i, t in enumerate(detail["transactions"], start=1):
        added = ", ".join(a["name"] for a in t["adds"]) or "nobody"
        dropped = ", ".join(d["name"] for d in t["drops"]) or "nobody"
        label = "claimed off waivers" if t["type"] == "WAIVER" else (
            "traded for" if t["type"] == "TRADE_ACCEPT" else "signed off free agency")
        add(f"transaction.{i}", f"{t['teamName']} {label} {added} and dropped {dropped}.")

    return facts


def season_records(year: int, week: int) -> dict[str, Any]:
    """Best and worst single-week performances so far this season."""
    weeks = regular_season_weeks(year, week)
    lines = []
    for w in weeks:
        for side in _sides(load_week(year, w)):
            lines.append({"week": w, "teamId": side["teamId"], "name": side["teamName"], "score": side["score"]})
    if not lines:
        return {}
    return {
        "highestWeek": max(lines, key=lambda x: x["score"]),
        "lowestWeek": min(lines, key=lambda x: x["score"]),
        "weeksPlayed": len(weeks),
    }


def build(year: int, week: int) -> dict[str, Any]:
    """Compute the week's fact pack and write it next to the raw snapshot."""
    league = load_league(year)
    standings = standings_through(year, week)
    allplay = all_play_through(year, week)
    detail = week_detail(year, week)
    records = season_records(year, week)

    pack = {
        "year": year,
        "week": week,
        "leagueName": league["name"],
        "teamCount": league["teamCount"],
        "playoffTeamCount": league["playoffTeamCount"],
        "regularSeasonWeeks": league["regularSeasonWeeks"],
        "standings": standings,
        "allPlay": allplay,
        "seasonRecords": records,
        **detail,
        "facts": _sentences(year, week, standings, allplay, detail),
    }

    if records:
        pack["facts"].extend(
            [
                {
                    "id": "season.highest",
                    "text": f"The season's highest single week is {records['highestWeek']['name']} with "
                            f"{_fmt(records['highestWeek']['score'])} in week {records['highestWeek']['week']}.",
                },
                {
                    "id": "season.lowest",
                    "text": f"The season's lowest single week is {records['lowestWeek']['name']} with "
                            f"{_fmt(records['lowestWeek']['score'])} in week {records['lowestWeek']['week']}.",
                },
            ]
        )

    facts_path(year, week).write_text(json.dumps(pack, indent=2) + "\n")
    return pack


def load_facts(year: int, week: int) -> dict[str, Any]:
    return json.loads(facts_path(year, week).read_text())
