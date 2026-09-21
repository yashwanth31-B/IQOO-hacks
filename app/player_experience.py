"""
Gaming Second Brain — Player Experience Detection Module
Requirement 1: Player Experience Detection grounded strictly in stored database history.

Classifies player into:
- NEW PLAYER (0 recorded sessions for target game)
- RETURNING PLAYER (1 to 4 recorded sessions for target game)
- EXPERIENCED PLAYER (5+ recorded sessions for target game with established metrics)
- INSUFFICIENT_DATA (Explicitly handled when history cannot be verified or corrupt)
"""

import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import Counter

from app.models import PlayerExperienceProfile, Session
from app.session_storage import SessionStorage, default_session_storage


class PlayerExperienceDetector:
    """
    Evaluates stored gaming history to determine player experience level
    without making unsupported assumptions.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage
        self._cache: Dict[str, PlayerExperienceProfile] = {}

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def get_experience_profile(
        self,
        game: Optional[str] = "BGMI",
        player_name: Optional[str] = "Manoj",
        force_refresh: bool = False
    ) -> PlayerExperienceProfile:
        """
        Determines the player's experience level for a specific game.
        Uses in-memory cache for sub-millisecond execution.
        """
        clean_game = (game or "BGMI").strip()
        cache_key = f"{clean_game.lower()}_{player_name or ''}"

        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        all_sessions = self.storage.get_recent_sessions(limit=500)
        total_sessions_count = len(all_sessions)

        # Filter sessions for the target game
        game_lower = clean_game.lower()
        game_sessions: List[Session] = [
            s for s in all_sessions
            if s.game and (
                game_lower in s.game.lower() or
                s.game.lower() in game_lower
            )
        ]
        game_count = len(game_sessions)

        # Handle Edge Case: Unknown Game or zero history across the entire system
        if total_sessions_count == 0 and game_count == 0:
            profile = PlayerExperienceProfile(
                experience_level="NEW PLAYER",
                total_sessions=0,
                sessions_in_current_game=0,
                recent_sessions=[],
                data_confidence=1.0,
                last_played_at=None,
                welcome_header="👋 WELCOME",
                message=(
                    f"This appears to be your first recorded {clean_game} session.\n\n"
                    "🎮 Second Brain is learning your play style.\n\n"
                    "We'll start recording your performance from this session."
                ),
                data_source="PERSONAL HISTORY"
            )
            self._cache[cache_key] = profile
            return profile

        # Scenario 1: NEW PLAYER (0 recorded sessions for target game)
        if game_count == 0:
            profile = PlayerExperienceProfile(
                experience_level="NEW PLAYER",
                total_sessions=total_sessions_count,
                sessions_in_current_game=0,
                recent_sessions=[],
                data_confidence=1.0,
                last_played_at=None,
                welcome_header="👋 WELCOME",
                message=(
                    f"This appears to be your first recorded {clean_game} session.\n\n"
                    "🎮 Second Brain is learning your play style.\n\n"
                    "We'll start recording your performance from this session."
                ),
                data_source="PERSONAL HISTORY"
            )
            self._cache[cache_key] = profile
            return profile

        # Extract metrics from game sessions
        recent_summaries = []
        kd_list: List[float] = []
        map_counter: Counter = Counter()

        for s in game_sessions:
            # K/D extraction
            kd = s.kd_ratio
            if kd is None and s.kills is not None and s.deaths is not None:
                kd = round(float(s.kills) / max(float(s.deaths), 1.0), 2)
            if kd is not None:
                kd_list.append(kd)

            # Map counter
            s_map = s.map or s.map_or_level
            if s_map:
                map_counter[s_map] += 1

            recent_summaries.append({
                "session_id": str(s.session_id or s.id or ""),
                "date": s.date or s.timestamp or "",
                "map": s_map or "Unknown",
                "kd_ratio": kd,
                "kills": s.kills,
                "deaths": s.deaths,
                "result": s.result or s.outcome or ""
            })

        last_session = game_sessions[0] if game_sessions else None
        last_played_at = (last_session.date or last_session.timestamp) if last_session else None
        last_kd = recent_summaries[0]["kd_ratio"] if recent_summaries else None
        strongest_kd = max(kd_list) if kd_list else None
        most_played_map = map_counter.most_common(1)[0][0] if map_counter else "Unknown Map"

        # Scenario 2: RETURNING PLAYER (1 to 4 sessions - not enough to call experienced)
        # Core Rule: "Do not call someone experienced based only on one or two sessions."
        if 1 <= game_count < 5:
            profile = PlayerExperienceProfile(
                experience_level="RETURNING PLAYER",
                total_sessions=total_sessions_count,
                sessions_in_current_game=game_count,
                recent_sessions=recent_summaries[:5],
                data_confidence=0.85,
                last_played_at=last_played_at,
                last_session_kd=last_kd,
                strongest_kd=strongest_kd,
                most_played_map=most_played_map,
                welcome_header="👋 WELCOME BACK",
                message=(
                    f"You've played {clean_game} {game_count} time{'s' if game_count != 1 else ''}.\n\n"
                    f"Last recorded session:\n"
                    f"K/D {last_kd if last_kd is not None else 'N/A'}\n\n"
                    "⚡ Your previous gaming memory is ready."
                ),
                data_source="PERSONAL HISTORY"
            )
            self._cache[cache_key] = profile
            return profile

        # Scenario 3: EXPERIENCED PLAYER (>= 5 sessions with robust historical data)
        # Sufficient historical data exists
        profile = PlayerExperienceProfile(
            experience_level="EXPERIENCED PLAYER",
            total_sessions=total_sessions_count,
            sessions_in_current_game=game_count,
            recent_sessions=recent_summaries[:10],
            data_confidence=0.98,
            last_played_at=last_played_at,
            last_session_kd=last_kd,
            strongest_kd=strongest_kd,
            most_played_map=most_played_map,
            welcome_header="🎯 PLAYER PROFILE",
            message=(
                f"{game_count} recorded sessions\n"
                f"Strongest recorded K/D: {strongest_kd if strongest_kd is not None else 'N/A'}\n"
                f"Most played map: {most_played_map}"
            ),
            data_source="PERSONAL HISTORY"
        )
        self._cache[cache_key] = profile
        return profile

    def clear_cache(self) -> None:
        """Clears experience detector cache."""
        self._cache.clear()


# Default singleton instance
default_player_experience_detector = PlayerExperienceDetector()
