import {
  factsSchema,
  leagueSchema,
  weekSnapshotSchema,
  type Facts,
  type League,
  type WeekSnapshot,
} from "./schema";

/**
 * Every page reads from the pipeline's committed JSON. Nothing here talks to
 * ESPN, so the site builds offline and a cookie expiry can never break a deploy.
 */

const factFiles = import.meta.glob<Record<string, unknown>>("/data/*/week_*.facts.json", { eager: true });
const leagueFiles = import.meta.glob<Record<string, unknown>>("/data/*/league.json", { eager: true });
const snapshotFiles = import.meta.glob<Record<string, unknown>>("/data/*/week_*.json", { eager: true });

function unwrap(mod: unknown): unknown {
  return (mod as { default?: unknown })?.default ?? mod;
}

function parseAll<T>(files: Record<string, unknown>, schema: { parse: (v: unknown) => T }, skip?: RegExp): T[] {
  return Object.entries(files)
    .filter(([path]) => !skip?.test(path))
    .map(([path, mod]) => {
      try {
        return schema.parse(unwrap(mod));
      } catch (error) {
        throw new Error(`${path} does not match the expected shape.\n${error}`);
      }
    });
}

export const leagues: League[] = parseAll(leagueFiles, leagueSchema).sort((a, b) => b.year - a.year);

export const allFacts: Facts[] = parseAll(factFiles, factsSchema).sort(
  (a, b) => b.year - a.year || b.week - a.week
);

// week_NN.facts.json also matches the raw-snapshot glob, so exclude it there.
export const snapshots: WeekSnapshot[] = parseAll(snapshotFiles, weekSnapshotSchema, /\.facts\.json$/).sort(
  (a, b) => b.year - a.year || b.week - a.week
);

/**
 * Every season we know about, newest first — including one that has been
 * created in ESPN but has not kicked off yet, so a new year appears in the
 * switcher the moment the league exists rather than after week 1.
 */
export const seasons: number[] = [
  ...new Set([...leagues.map((l) => l.year), ...allFacts.map((f) => f.year)]),
].sort((a, b) => b - a);

/** Seasons with at least one played week. */
export const playedSeasons: number[] = [...new Set(allFacts.map((f) => f.year))].sort((a, b) => b - a);

export function hasPlayedWeeks(year: number): boolean {
  return allFacts.some((f) => f.year === year);
}

/** Most recent season that actually has games in it. */
export const currentSeason: number = playedSeasons[0] ?? seasons[0];

export function leagueFor(year: number): League | undefined {
  return leagues.find((l) => l.year === year);
}

export function factsFor(year: number, week: number): Facts | undefined {
  return allFacts.find((f) => f.year === year && f.week === week);
}

export function snapshotFor(year: number, week: number): WeekSnapshot | undefined {
  return snapshots.find((s) => s.year === year && s.week === week);
}

/** Weeks of a season, newest first. Sorted numerically, so 10 follows 9. */
export function weeksOf(year: number): number[] {
  return allFacts.filter((f) => f.year === year).map((f) => f.week).sort((a, b) => b - a);
}

export function latestFacts(year?: number): Facts | undefined {
  return year ? allFacts.find((f) => f.year === year) : allFacts[0];
}

/** Every score a team recorded, oldest week first — the sparkline series. */
export function teamScoreSeries(year: number, teamId: number): { week: number; score: number }[] {
  return allFacts
    .filter((f) => f.year === year)
    .sort((a, b) => a.week - b.week)
    .flatMap((f) => {
      const entry = f.teamScores.find((t) => t.teamId === teamId);
      return entry ? [{ week: f.week, score: entry.score }] : [];
    });
}

/** A team's result in every week, oldest first. */
export function teamResults(year: number, teamId: number) {
  return allFacts
    .filter((f) => f.year === year)
    .sort((a, b) => a.week - b.week)
    .flatMap((f) => {
      const m = f.matchups.find((x) => x.winnerTeamId === teamId || x.loserTeamId === teamId);
      if (!m) return [];
      const won = m.winnerTeamId === teamId && !m.isTie;
      return [{
        week: f.week,
        won,
        tied: m.isTie,
        score: won ? m.winnerScore : m.loserScore,
        opponentScore: won ? m.loserScore : m.winnerScore,
        opponentName: won ? m.loserName : m.winnerName,
        opponentId: won ? m.loserTeamId : m.winnerTeamId,
      }];
    });
}

/** Current display name for a team, taken from the most recent week. */
export function teamName(year: number, teamId: number): string {
  const latest = latestFacts(year);
  return latest?.standings.find((r) => r.teamId === teamId)?.name ?? `Team ${teamId}`;
}
