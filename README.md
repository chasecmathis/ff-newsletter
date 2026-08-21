# Pressbox

Weekly newsletter and stats site for a 12-team home fantasy football league.
Live at **https://chasecmathis.github.io/ff-newsletter/**

Two halves that share one committed dataset:

- **`pipeline/`** — Python. Pulls ESPN data, derives every stat, drafts the
  newsletter with Claude, and checks the draft against the data.
- **`src/`** — Astro. Static site built from the JSON in `data/` and the prose
  in `content/`.

## Why it's built this way

The newsletter used to be one big prompt: dump the whole season into Gemini and
ask for prose. It made things up — a player on the wrong NFL team, a rookie who
wasn't a rookie, a score that never happened.

The cause was asking the model to do two things it's bad at: recall biographical
facts about real players, and transcribe twelve-row tables into prose. Both jobs
are gone now.

```
ESPN ──ingest──► data/2025/week_06.json      raw snapshot, committed
                        │
                    facts.py                  all derivation, exactly once
                        │
               data/2025/week_06.facts.json
                  ╱                  ╲
       the site renders          Claude writes
       tables and panels         prose only
```

**The site and the newsletter read the same file.** The prose can't contradict
the standings table, because neither of them computed anything — `facts.py` did.
The model is handed labelled facts, told they are the only true statements it
has, and asked for writing that cites the ids it used. It never writes a table.

Then `verify.py` checks every number and name in the draft against the fact pack
before you read it.

## Weekly routine

First time only:

```bash
cd pipeline && uv sync && cd ..
```

Then, from the repo root — `./ffnews` is a wrapper, so there is nothing to
activate and nothing to put on your PATH:

```bash
./ffnews ingest --year 2025 --weeks 7     # pull the week from ESPN
./ffnews facts  --year 2025 --weeks 7     # derive the stats
./ffnews draft  --year 2025 --week 7      # Claude writes it; both verifier passes run

# read content/newsletters/2025/week-07.md, edit whatever you want, then:
./ffnews publish --year 2025 --week 7
git add -A && git commit -m "Week 7" && git push
```

To drop the `./` and run `ffnews` from anywhere, add this to `~/.zshrc`:

```bash
alias ffnews="/Users/chasemathis/Desktop/Personal/Code/ffnews/ffnews"
```

Nothing reaches the site until you run `publish` — the frontmatter carries
`status: draft` and the build skips drafts.

`draft` runs two checks on its own output. The deterministic pass resolves every
number and name against the fact pack. The Claude pass then reads for claims that
are wrong without being fabricated — a count that's off, a comparison that
doesn't hold, a player attributed to the wrong roster. Expect it to surface one
or two things per draft; that is what the human review is for.

Add `--quick` to skip the audit pass. Other commands: `ffnews standings --year
2025`, `ffnews verify --year 2025 --week 7`.

## Keeping the voice yours

`data/2025/storylines.json` holds the running jokes, nicknames and rivalries. It
is hand-edited and fed into every draft. Callbacks are most of what separates a
league newsletter from generated text, so it is worth keeping current.

The style rules live in `pipeline/ffnews/prompts/voice.md`, including a list of
phrases to never use. Edit it whenever something reads wrong.

## Site

```bash
npm install
npm run dev        # http://localhost:4321/ff-newsletter/
npm run build
```

Pushing to `main` deploys via GitHub Actions. CI only builds static files — the
ESPN cookies and API key never leave your machine.

Design is "Pressbox": prose on a chalk-white stat sheet, numbers on a black
scoreboard. Tokens are in `src/styles/global.css`.

## Things that will break

- **ESPN cookies expire every few months.** `ffnews ingest` will tell you when
  that has happened. Refresh `ESPN_SWID` and `ESPN_S2` in `.env`.
- **Playoff weeks are excluded from weekly stats.** This league's playoffs run
  as one matchup across two scoring periods, and ESPN reports the same
  cumulative total under both. Those numbers are roughly double a normal week,
  so folding them into standings or records would corrupt them. Regular-season
  weeks only.
- **Team names change mid-season.** Everything is keyed on `teamId`; each
  snapshot also stores the name in effect that week.
