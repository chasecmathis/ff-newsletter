import { z } from "astro/zod";

/**
 * Runtime shape of the pipeline output. Validating at build time means a
 * malformed data file fails `astro build` loudly instead of rendering a blank
 * page in production.
 */

export const playerSchema = z.object({
  playerId: z.number().nullable(),
  name: z.string(),
  position: z.string(),
  slot: z.string(),
  started: z.boolean(),
  proTeam: z.string(),
  proOpponent: z.string(),
  points: z.number(),
  projected: z.number(),
  injuryStatus: z.string().nullable(),
  onByeWeek: z.boolean(),
});

const namedPlayer = playerSchema.extend({
  teamId: z.number(),
  teamName: z.string(),
});

export const standingsRowSchema = z.object({
  rank: z.number(),
  teamId: z.number(),
  name: z.string(),
  wins: z.number(),
  losses: z.number(),
  ties: z.number(),
  record: z.string(),
  pointsFor: z.number(),
  pointsAgainst: z.number(),
  streak: z.string(),
});

export const allPlayRowSchema = z.object({
  rank: z.number(),
  teamId: z.number(),
  name: z.string(),
  allPlayWins: z.number(),
  allPlayLosses: z.number(),
  allPlayRecord: z.string(),
  allPlayPct: z.number(),
  luck: z.number(),
});

export const matchupSchema = z.object({
  winnerTeamId: z.number(),
  winnerName: z.string(),
  winnerScore: z.number(),
  loserTeamId: z.number(),
  loserName: z.string(),
  loserScore: z.number(),
  margin: z.number(),
  isTie: z.boolean(),
});

export const efficiencySchema = z.object({
  teamId: z.number(),
  name: z.string(),
  actual: z.number(),
  optimal: z.number(),
  pointsLeftOnBench: z.number(),
  efficiencyPct: z.number(),
  worstDecision: z
    .object({
      slot: z.string(),
      startedName: z.string(),
      startedPoints: z.number(),
      benchedName: z.string(),
      benchedPoints: z.number(),
      pointsLost: z.number(),
    })
    .nullable(),
});

export const factsSchema = z.object({
  year: z.number(),
  week: z.number(),
  leagueName: z.string(),
  teamCount: z.number(),
  playoffTeamCount: z.number(),
  regularSeasonWeeks: z.number(),
  standings: z.array(standingsRowSchema),
  allPlay: z.array(allPlayRowSchema),
  matchups: z.array(matchupSchema),
  efficiency: z.array(efficiencySchema),
  teamScores: z.array(z.object({ teamId: z.number(), name: z.string(), score: z.number() })),
  highestTeam: z.object({ teamId: z.number(), name: z.string(), score: z.number() }),
  lowestTeam: z.object({ teamId: z.number(), name: z.string(), score: z.number() }),
  closestGame: matchupSchema,
  biggestBlowout: matchupSchema,
  positionLeaders: z.record(
    z.string(),
    z.object({
      bestStarted: namedPlayer,
      worstStarted: namedPlayer,
      bestBenched: namedPlayer.nullable(),
    })
  ),
  projections: z.object({
    biggestBoom: namedPlayer.extend({ delta: z.number() }).nullable(),
    biggestBust: namedPlayer.extend({ delta: z.number() }).nullable(),
  }),
  transactionsAvailable: z.boolean().default(true),
  transactions: z.array(
    z.object({
      type: z.string(),
      teamId: z.number().nullable(),
      teamName: z.string(),
      date: z.number().nullable(),
      adds: z.array(z.object({ playerId: z.number().nullable(), name: z.string() })),
      drops: z.array(z.object({ playerId: z.number().nullable(), name: z.string() })),
    })
  ),
  seasonRecords: z.object({
    highestWeek: z.object({ week: z.number(), teamId: z.number(), name: z.string(), score: z.number() }),
    lowestWeek: z.object({ week: z.number(), teamId: z.number(), name: z.string(), score: z.number() }),
    weeksPlayed: z.number(),
  }),
  facts: z.array(z.object({ id: z.string(), text: z.string() })),
});

export const leagueSchema = z.object({
  year: z.number(),
  name: z.string(),
  teamCount: z.number(),
  regularSeasonWeeks: z.number(),
  playoffTeamCount: z.number(),
  teams: z.array(
    z.object({
      teamId: z.number(),
      name: z.string(),
      abbrev: z.string(),
      owners: z.array(z.string()),
      logo: z.string(),
      divisionId: z.number(),
    })
  ),
});

export const weekSnapshotSchema = z.object({
  year: z.number(),
  week: z.number(),
  matchups: z.array(
    z.object({
      home: z.object({
        teamId: z.number(),
        teamName: z.string(),
        score: z.number(),
        projected: z.number(),
        lineup: z.array(playerSchema),
      }),
      away: z.object({
        teamId: z.number(),
        teamName: z.string(),
        score: z.number(),
        projected: z.number(),
        lineup: z.array(playerSchema),
      }),
      isPlayoff: z.boolean(),
    })
  ),
  transactionsAvailable: z.boolean().default(true),
});

export type Facts = z.infer<typeof factsSchema>;
export type League = z.infer<typeof leagueSchema>;
export type WeekSnapshot = z.infer<typeof weekSnapshotSchema>;
export type StandingsRow = z.infer<typeof standingsRowSchema>;
export type AllPlayRow = z.infer<typeof allPlayRowSchema>;
export type Matchup = z.infer<typeof matchupSchema>;
export type Efficiency = z.infer<typeof efficiencySchema>;
