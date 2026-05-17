"""Quick start: load 2026 MLB data into pandas DataFrames."""

from mlb_stats import DEFAULT_SEASON, MLBClient


def main() -> None:
    client = MLBClient(season=DEFAULT_SEASON)

    print(f"=== {client.season} MLB teams ===")
    teams = client.teams()
    print(teams[["team_id", "name", "abbreviation", "division"]])

    print("\n=== Cubs roster ===")
    roster = client.team_roster("CHC")
    print(roster[["player_id", "name", "position", "jersey_number"]].head(10))

    print("\n=== Cubs team hitting (season) ===")
    team_hitting = client.team_stats("CHC", group="hitting")
    print(team_hitting[["avg", "homeRuns", "runs", "hits", "ops"]])

    print("\n=== Cubs player hitting ===")
    player_hitting = client.team_player_stats("CHC", group="hitting")
    cols = ["name", "gamesPlayed", "avg", "homeRuns", "rbi", "ops"]
    cols = [c for c in cols if c in player_hitting.columns]
    print(player_hitting[cols].sort_values("homeRuns", ascending=False).head(10))

    print("\n=== Pete Crow-Armstron (individual) ===")
    pete = client.search_players("Pete Crow-Armstrong")
    print(pete)
    pete_stats = client.player_stats("Pete Crow-Armstrong", group="hitting")
    print(pete_stats[["avg", "homeRuns", "rbi", "ops", "gamesPlayed"]])


if __name__ == "__main__":
    main()
