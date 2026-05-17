"""Quick start: load 2026 MLB data into pandas DataFrames."""

from mlb_stats import DEFAULT_SEASON, MLBClient


def main() -> None:
    client = MLBClient(season=DEFAULT_SEASON)

    print(f"=== {client.season} MLB teams ===")
    teams = client.teams()
    print(teams[["team_id", "name", "abbreviation", "division"]].head())

    print("\n=== Yankees roster ===")
    roster = client.team_roster("NYY")
    print(roster[["player_id", "name", "position", "jersey_number"]].head(10))

    print("\n=== Yankees team hitting (season) ===")
    team_hitting = client.team_stats("NYY", group="hitting")
    print(team_hitting[["avg", "homeRuns", "runs", "hits", "ops"]])

    print("\n=== Yankees player hitting ===")
    player_hitting = client.team_player_stats("NYY", group="hitting")
    cols = ["name", "gamesPlayed", "avg", "homeRuns", "rbi", "ops"]
    cols = [c for c in cols if c in player_hitting.columns]
    print(player_hitting[cols].sort_values("homeRuns", ascending=False).head(10))

    print("\n=== Aaron Judge (individual) ===")
    judge = client.search_players("Aaron Judge")
    print(judge)
    judge_stats = client.player_stats("Aaron Judge", group="hitting")
    print(judge_stats[["avg", "homeRuns", "rbi", "ops", "gamesPlayed"]])


if __name__ == "__main__":
    main()
