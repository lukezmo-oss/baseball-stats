"""Fetch MLB team and player data via the public Stats API."""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd
import requests

DEFAULT_SEASON = 2026

StatGroup = Literal["hitting", "pitching", "fielding"]
BASE_URL = "https://statsapi.mlb.com/api/v1"


class MLBClient:
    """Client for MLB Stats API (https://statsapi.mlb.com). No API key required."""

    def __init__(self, season: int = DEFAULT_SEASON, timeout: float = 30.0):
        self.season = season
        self.timeout = timeout
        self._session = requests.Session()
        self._teams_cache: pd.DataFrame | None = None

    def _get(self, path: str, **params) -> dict:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        response = self._session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def teams(self, *, refresh: bool = False) -> pd.DataFrame:
        """All MLB teams for the configured season."""
        if self._teams_cache is not None and not refresh:
            return self._teams_cache.copy()

        data = self._get("teams", sportId=1, season=self.season)
        rows = [
            {
                "team_id": t["id"],
                "name": t["name"],
                "abbreviation": t["abbreviation"],
                "team_name": t.get("teamName"),
                "location": t.get("locationName"),
                "league": t.get("league", {}).get("name"),
                "division": t.get("division", {}).get("name"),
            }
            for t in data["teams"]
        ]
        self._teams_cache = pd.DataFrame(rows).sort_values("name").reset_index(drop=True)
        return self._teams_cache.copy()

    def resolve_team(self, team: str | int) -> int:
        """Resolve team id from numeric id, abbreviation, or name fragment."""
        if isinstance(team, int):
            return team

        teams_df = self.teams()
        key = str(team).strip().lower()

        exact = teams_df[
            (teams_df["abbreviation"].str.lower() == key)
            | (teams_df["name"].str.lower() == key)
            | (teams_df["team_name"].str.lower() == key)
        ]
        if len(exact) == 1:
            return int(exact.iloc[0]["team_id"])

        partial = teams_df[
            teams_df["name"].str.lower().str.contains(key, regex=False)
            | teams_df["team_name"].str.lower().str.contains(key, regex=False)
            | teams_df["location"].str.lower().str.contains(key, regex=False)
        ]
        if len(partial) == 1:
            return int(partial.iloc[0]["team_id"])
        if len(partial) == 0:
            raise ValueError(f"No team matching {team!r} for season {self.season}")
        matches = partial[["team_id", "name", "abbreviation"]].to_string(index=False)
        raise ValueError(f"Ambiguous team {team!r}. Matches:\n{matches}")

    def team_roster(self, team: str | int, *, roster_type: str = "active") -> pd.DataFrame:
        """Active (or 40-man, etc.) roster for a team."""
        team_id = self.resolve_team(team)
        data = self._get(
            f"teams/{team_id}/roster",
            season=self.season,
            rosterType=roster_type,
        )
        rows = []
        for entry in data.get("roster", []):
            person = entry["person"]
            position = entry.get("position", {})
            rows.append(
                {
                    "player_id": person["id"],
                    "name": person["fullName"],
                    "position": position.get("abbreviation"),
                    "position_type": position.get("type"),
                    "jersey_number": entry.get("jerseyNumber"),
                    "status": entry.get("status", {}).get("description"),
                    "team_id": team_id,
                    "season": self.season,
                }
            )
        return pd.DataFrame(rows)

    def team_stats(
        self,
        team: str | int,
        *,
        group: StatGroup = "hitting",
    ) -> pd.Series:
        """Season aggregate stats for one team."""
        team_id = self.resolve_team(team)
        data = self._get(
            f"teams/{team_id}/stats",
            stats="season",
            season=self.season,
            group=group,
        )
        split = data["stats"][0]["splits"][0]
        stats = pd.Series(split["stat"], name="value")
        stats["team_id"] = team_id
        stats["season"] = self.season
        stats["group"] = group
        return stats

    def team_player_stats(
        self,
        team: str | int,
        *,
        group: StatGroup = "hitting",
    ) -> pd.DataFrame:
        """Season stats for every player on a team."""
        team_id = self.resolve_team(team)
        data = self._get(
            "stats",
            stats="season",
            season=self.season,
            group=group,
            teamId=team_id,
            playerPool="ALL",
        )
        return self._splits_to_dataframe(data, group=group)

    def search_players(self, name: str) -> pd.DataFrame:
        """Search players by name (useful before looking up stats)."""
        data = self._get("people/search", names=name)
        rows = [
            {
                "player_id": p["id"],
                "name": p["fullName"],
                "primary_position": p.get("primaryPosition", {}).get("abbreviation"),
                "current_team": p.get("currentTeam", {}).get("name"),
                "current_team_id": p.get("currentTeam", {}).get("id"),
                "bat_side": p.get("batSide", {}).get("code"),
                "pitch_hand": p.get("pitchHand", {}).get("code"),
            }
            for p in data.get("people", [])
        ]
        return pd.DataFrame(rows)

    def player_stats(
        self,
        player: str | int,
        *,
        group: StatGroup = "hitting",
    ) -> pd.Series:
        """Season stats for one player (id or exact full name)."""
        player_id = self._resolve_player(player)
        data = self._get(
            f"people/{player_id}/stats",
            stats="season",
            season=self.season,
            group=group,
        )
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            raise ValueError(f"No {group} stats for player {player_id} in {self.season}")
        stats = pd.Series(splits[0]["stat"], name="value")
        stats["player_id"] = player_id
        stats["season"] = self.season
        stats["group"] = group
        return stats

    def _resolve_player(self, player: str | int) -> int:
        if isinstance(player, int):
            return player
        matches = self.search_players(str(player))
        if matches.empty:
            raise ValueError(f"No player matching {player!r}")
        exact = matches[matches["name"].str.lower() == str(player).strip().lower()]
        if len(exact) == 1:
            return int(exact.iloc[0]["player_id"])
        if len(matches) == 1:
            return int(matches.iloc[0]["player_id"])
        listing = matches[["player_id", "name", "current_team"]].to_string(index=False)
        raise ValueError(f"Ambiguous player {player!r}. Matches:\n{listing}")

    def _splits_to_dataframe(self, data: dict, *, group: str) -> pd.DataFrame:
        splits = data.get("stats", [{}])[0].get("splits", [])
        rows = []
        for split in splits:
            row = dict(split.get("stat", {}))
            player = split.get("player", {})
            if player:
                row["player_id"] = player.get("id")
                row["name"] = player.get("fullName")
            team = split.get("team", {})
            if team:
                row["team_id"] = team.get("id")
                row["team"] = team.get("name")
            row["season"] = self.season
            row["group"] = group
            rows.append(row)
        df = pd.DataFrame(rows)
        if "name" in df.columns:
            col_order = ["player_id", "name"] + [c for c in df.columns if c not in ("player_id", "name")]
            df = df[col_order]
        return self._coerce_numeric_columns(df)

    @staticmethod
    def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        for col in out.columns:
            if col in ("player_id", "team_id", "season", "name", "team", "group"):
                continue
            if out[col].dtype != object:
                continue
            numeric = out[col].map(_to_float)
            if numeric.notna().mean() > 0.5:
                out[col] = numeric
        return out


def _to_float(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NA
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text == "-":
        return pd.NA
    try:
        return float(text)
    except ValueError:
        if text.startswith(".") and re.fullmatch(r"\.\d+", text):
            return float("0" + text)
        return pd.NA
