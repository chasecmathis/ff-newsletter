from espn_api.football import League
import google.generativeai as genai
import pathlib
import os
from dotenv import load_dotenv
import datetime
from collections import defaultdict


def generate_newsletter_prompt(current_week, year):
    league = League(league_id=os.getenv("ESPN_LEAGUE_ID", -1), year=year, swid=os.getenv("ESPN_SWID"),
                    espn_s2=os.getenv("ESPN_S2"))

    # Cache for box scores to avoid repeated API calls
    box_scores_cache = {}

    def get_box_scores(week):
        if week not in box_scores_cache:
            try:
                box_scores_cache[week] = league.box_scores(week)
            except:
                box_scores_cache[week] = None
        return box_scores_cache[week]

    # Create a player-to-team mapping for faster lookups
    player_to_team_map = {}

    def build_player_team_map(box_scores):
        if not box_scores:
            return
        for matchup in box_scores:
            for player in matchup.home_lineup:
                player_to_team_map[player.name] = matchup.home_team.team_name
            for player in matchup.away_lineup:
                player_to_team_map[player.name] = matchup.away_team.team_name

    # Function to find which team a player belongs to
    def find_player_team(player, box_scores):
        return player_to_team_map.get(player.name, "Unknown")
    
    # Determine league context
    def get_league_context(current_week):
        # Standard ESPN leagues: Weeks 15-17 are playoffs
        if current_week >= 14:
            return "PLAYOFF WEEKS"
        elif current_week >= 12:
            return "PLAYOFF RACE - Teams fighting for playoff positioning"
        else:
            return "REGULAR SEASON"
    
    league_context = get_league_context(current_week)

    prompt = f"""
You are a witty fantasy football newsletter writer. Create an entertaining weekly newsletter for our league.

CURRENT WEEK: {current_week}
YEAR: {year}
LEAGUE CONTEXT: {league_context}

STANDINGS:
"""
    # Calculate wins/losses up to current_week for each team
    weekly_standings = league.standings_weekly(current_week)
    for i, team in enumerate(weekly_standings, 1):
        wins_at_week = 0
        losses_at_week = 0
        points_for_at_week = 0

        # Count wins/losses up to and including current_week
        for week in range(1, current_week + 1):
            box_scores = get_box_scores(week)
            if not box_scores:
                continue

            for matchup in box_scores:
                team_score = team_opponent_score = 0
                if matchup.home_team.team_id == team.team_id:
                    team_score, team_opponent_score = matchup.home_score, matchup.away_score
                elif matchup.away_team.team_id == team.team_id:
                    team_score, team_opponent_score = matchup.away_score, matchup.home_score
                else:
                    continue

                points_for_at_week += team_score
                if team_score > team_opponent_score:
                    wins_at_week += 1
                else:
                    losses_at_week += 1

        prompt += f"{i}. {team.team_name} - {wins_at_week}-{losses_at_week} - {points_for_at_week:.1f} PF\n"

    prompt += "\nPOWER RANKINGS:\n"
    power_rankings = league.power_rankings(week=current_week - 1 if current_week > 1 else 1)
    for i, (power_score, team) in enumerate(power_rankings, 1):
        prompt += f"{i}. {team.team_name} - Power Score: {float(power_score):.2f}\n"

    # Current week box scores with full lineups (if available)
    current_box_scores = get_box_scores(current_week)
    if current_box_scores:
        prompt += f"\nCURRENT WEEK {current_week} MATCHUPS WITH LINEUPS:\n"

        for matchup in current_box_scores:
            # Determine matchup stakes
            matchup_stakes = ""
            if league_context == "PLAYOFF WEEKS":
                matchup_stakes = " [PLAYOFF MATCHUP]"
            elif league_context.startswith("PLAYOFF RACE"):
                matchup_stakes = " [PLAYOFF IMPLICATIONS]"
            
            prompt += f"\n{matchup.away_team.team_name} vs {matchup.home_team.team_name}{matchup_stakes}\n"

            # Team lineups with bench info
            for team_name, lineup in [(matchup.away_team.team_name, matchup.away_lineup),
                                      (matchup.home_team.team_name, matchup.home_lineup)]:
                prompt += f"{team_name} Starters:\n"
                bench_players = []
                
                for player in lineup:
                    if player.slot_position not in ['BE', 'IR']:
                        prompt += f"  {player.slot_position}: {player.name} ({player.position}) - {player.points:.1f} pts\n"
                    elif player.slot_position == 'BE':
                        bench_players.append(f"{player.name} ({player.position}) - {player.points:.1f}")
                
                # Include top bench performers
                if bench_players:
                    bench_sorted = sorted(bench_players, key=lambda x: float(x.split(' - ')[1]), reverse=True)
                    prompt += f"  Top Bench: {bench_sorted[0] if bench_sorted else 'None'}\n"

            prompt += f"Score: {matchup.away_team.team_name} {matchup.away_score:.1f} - {matchup.home_team.team_name} {matchup.home_score:.1f}\n"
    else:
        prompt += f"\nCurrent week matchups: Data not yet available\n"

    # Include previous weeks data with enhanced analysis
    prompt += "\nPREVIOUS WEEKS RESULTS:\n"
    for week in range(1, current_week):
        box_scores = get_box_scores(week)
        if box_scores:
            # Build player team map for this week for faster lookups
            build_player_team_map(box_scores)

            prompt += f"\nWEEK {week} RESULTS:\n"

            # Track close games and blowouts for better commentary
            close_games = []
            blowouts = []

            for matchup in box_scores:
                away_trophy = "🏆" if matchup.away_score > matchup.home_score else ""
                home_trophy = "🏆" if matchup.home_score > matchup.away_score else ""
                
                score_diff = abs(matchup.away_score - matchup.home_score)
                if score_diff <= 5:
                    close_games.append(f"{matchup.away_team.team_name} vs {matchup.home_team.team_name} ({score_diff:.1f} pt diff)")
                elif score_diff >= 30:
                    winner = matchup.away_team.team_name if matchup.away_score > matchup.home_score else matchup.home_team.team_name
                    blowouts.append(f"{winner} dominated ({score_diff:.1f} pt margin)")
                
                prompt += f"{matchup.away_team.team_name} {matchup.away_score:.1f} {away_trophy} vs {matchup.home_team.team_name} {matchup.home_score:.1f} {home_trophy}\n"
            
            # Add game context
            if close_games:
                prompt += f"  Nail-biters: {', '.join(close_games)}\n"
            if blowouts:
                prompt += f"  Blowouts: {', '.join(blowouts)}\n"

            # Get best/worst performers for the most recent 2 weeks only (to keep prompt manageable)
            if week >= current_week - 2:
                players_by_position = defaultdict(list)
                for matchup in box_scores:
                    for player in matchup.home_lineup + matchup.away_lineup:
                        if player.slot_position not in ['BE', 'IR'] and player.points > 0:
                            players_by_position[player.position].append(player)

                # Only show best performers to keep it concise
                prompt += f"  Week {week} Stars:\n"
                for position in ['QB', 'RB', 'WR', 'TE']:
                    if position in players_by_position and players_by_position[position]:
                        best_player = max(players_by_position[position], key=lambda x: x.points)
                        team_name = find_player_team(best_player, box_scores)
                        prompt += f"    {position}: {best_player.name} ({team_name}) - {best_player.points:.1f} pts\n"
        else:
            prompt += f"Week {week}: Data unavailable\n"

    prompt += f"""

Write a fun 1000-1400 word newsletter that:
1. Has an engaging title that captures the season's storylines and league context ({league_context})
2. Displays the current standings and power rankings in nicely formatted tables
3. Analyzes current standings and power rankings with humor, considering the league context
4. Reviews the current week's matchups and starting lineups with commentary
5. Highlights bench performances and lineup decisions (who started the wrong players?)
6. Reviews trends and patterns from previous weeks (close games, blowouts, consistency)
7. Includes team-specific analysis and friendly trash talk
8. If playoff context: emphasize playoff implications, elimination scenarios, and championship hopes
9. If regular season: focus on early trends, overreactions, and building storylines
10. Builds excitement for what's at stake in upcoming weeks

Keep it entertaining with fantasy football humor and league-specific commentary!
"""

    return prompt


def generate_newsletter(current_week, year, api_key):
    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    # Generate the prompt
    prompt = generate_newsletter_prompt(current_week, year)

    # Generate the newsletter using Gemini
    try:
        response = model.generate_content(prompt)
        front_matter = f"""---
layout: default
title: "Week {current_week}"
week: {current_week}
year: {year}
date: {datetime.datetime.now().strftime('%Y-%m-%d')}
permalink: /newsletters/{year}/week_{current_week}/
categories: {year}
feature_text: |
  ## Week {current_week} Fantasy Report 🏈
  Hype Trains, Heartbreak, Matchups, and More!
excerpt: "Week {current_week} of the {year} season recap with all the drama, surprises, and fantasy insights you need."
---

"""
        return front_matter + response.text
    except Exception as e:
        return f"Error generating newsletter: {str(e)}"


if __name__ == "__main__":
    current_year = int(input("Enter the year: "))
    current_week = int(input("Enter the current week number: "))

    # Ask user if they want to use Gemini or just get the prompt
    use_gemini = input("Generate newsletter with Gemini? (y/n): ").lower().strip() == 'y'

    load_dotenv()
    prompt = generate_newsletter_prompt(current_week, current_year)

    if use_gemini:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            print("Generating newsletter...")
            newsletter = generate_newsletter(current_week, current_year, api_key)
            try:
                path = pathlib.Path(f"./newsletters/{current_year}/week_{current_week}.md")
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_text(newsletter)
            except IOError as e:
                print(f"Error writing to file: {e}")

    print("Newsletter Prompt for Google Gemini:")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
