import json
import sqlite3
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from collections import Counter

from app.models import Session, ProfileFact, PlayerProfile
from app.session_storage import SessionStorage, default_session_storage
from app.database import get_db_connection


NOT_ENOUGH_DATA = "Not enough data to determine this."
MIN_EVIDENCE_SESSIONS = 2


# =====================================================================
# PHASE 6: PLAYER PROFILE MANAGER
# =====================================================================

class PlayerProfileManager:
    """
    Builds and maintains lightweight long-term player profile memory (Phase 6).
    
    Adheres strictly to core rules:
    - Never assumes a preference from one session.
    - Only identifies preferences when multiple stored sessions (>= 2) support them.
    - Every important profile fact has explicit evidence session IDs.
    - Uses 'Not enough data to determine this.' when data is insufficient.
    - Dynamically updates profile information as new sessions are processed.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Ensures player_profile table exists in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_key TEXT UNIQUE NOT NULL,
            profile_value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            evidence_json TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        conn.close()

    def build_profile(
        self,
        sessions: List[Session],
        memories: Optional[List[Dict[str, Any]]] = None
    ) -> PlayerProfile:
        """
        Synthesizes the 6 core profile memory dimensions from stored sessions:
        1. preferred_game
        2. frequently_played_maps
        3. frequently_used_configurations
        4. preferred_session_duration
        5. recurring_strengths
        6. recurring_improvement_areas
        """
        # RULE: Never assume preferences from a single session.
        if not sessions or len(sessions) < MIN_EVIDENCE_SESSIONS:
            return PlayerProfile(
                preferred_game=self._insufficient_fact(),
                frequently_played_maps=self._insufficient_fact(),
                frequently_used_configurations=self._insufficient_fact(),
                preferred_session_duration=self._insufficient_fact(),
                recurring_strengths=self._insufficient_fact(),
                recurring_improvement_areas=self._insufficient_fact(),
                total_sessions_analyzed=len(sessions) if sessions else 0,
                last_updated=datetime.now().isoformat()
            )

        pref_game = self._analyze_preferred_game(sessions)
        freq_maps = self._analyze_frequently_played_maps(sessions)
        freq_configs = self._analyze_frequently_used_configurations(sessions)
        pref_duration = self._analyze_preferred_session_duration(sessions)
        rec_strengths = self._analyze_recurring_strengths(sessions, memories)
        rec_improvements = self._analyze_recurring_improvement_areas(sessions, memories)

        return PlayerProfile(
            preferred_game=pref_game,
            frequently_played_maps=freq_maps,
            frequently_used_configurations=freq_configs,
            preferred_session_duration=pref_duration,
            recurring_strengths=rec_strengths,
            recurring_improvement_areas=rec_improvements,
            total_sessions_analyzed=len(sessions),
            last_updated=datetime.now().isoformat()
        )

    def _insufficient_fact(self) -> ProfileFact:
        return ProfileFact(
            value=NOT_ENOUGH_DATA,
            evidence_session_ids=[],
            confidence=0.0,
            status="insufficient_data"
        )

    # 1. Preferred Game
    def _analyze_preferred_game(self, sessions: List[Session]) -> ProfileFact:
        game_to_ids: Dict[str, List[str]] = {}
        for s in sessions:
            if s.game:
                sid = str(s.session_id or s.id or "")
                game_to_ids.setdefault(s.game, []).append(sid)

        if not game_to_ids:
            return self._insufficient_fact()

        # Find top game
        sorted_games = sorted(game_to_ids.items(), key=lambda item: len(item[1]), reverse=True)
        top_game, top_ids = sorted_games[0]

        if len(top_ids) >= MIN_EVIDENCE_SESSIONS:
            confidence = round(min(1.0, len(top_ids) / len(sessions) + 0.2), 2)
            return ProfileFact(
                value=top_game,
                evidence_session_ids=top_ids,
                confidence=confidence,
                status="determined"
            )

        return self._insufficient_fact()

    # 2. Frequently Played Maps
    def _analyze_frequently_played_maps(self, sessions: List[Session]) -> ProfileFact:
        map_to_ids: Dict[str, List[str]] = {}
        for s in sessions:
            if s.map:
                sid = str(s.session_id or s.id or "")
                map_to_ids.setdefault(s.map, []).append(sid)

        # Filter maps with >= 2 sessions
        qualifying = [
            (map_name, ids) for map_name, ids in map_to_ids.items()
            if len(ids) >= MIN_EVIDENCE_SESSIONS
        ]

        if not qualifying:
            return self._insufficient_fact()

        qualifying.sort(key=lambda item: len(item[1]), reverse=True)
        formatted_maps = [f"{m} ({len(ids)} sessions)" for m, ids in qualifying]
        all_evidence = []
        for _, ids in qualifying:
            all_evidence.extend(ids)

        return ProfileFact(
            value=", ".join(formatted_maps),
            evidence_session_ids=list(dict.fromkeys(all_evidence)),
            confidence=0.9,
            status="determined"
        )

    # 3. Frequently Used Configurations
    def _analyze_frequently_used_configurations(self, sessions: List[Session]) -> ProfileFact:
        config_to_ids: Dict[str, List[str]] = {}
        for s in sessions:
            if s.configuration:
                sid = str(s.session_id or s.id or "")
                cfg_str = ""
                if isinstance(s.configuration, dict):
                    weapon = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
                    if weapon:
                        cfg_str = f"{weapon} configuration"
                    else:
                        cfg_str = "Custom tactical loadout"
                elif isinstance(s.configuration, str) and s.configuration.strip():
                    cfg_str = s.configuration.strip()

                if cfg_str:
                    config_to_ids.setdefault(cfg_str, []).append(sid)

        qualifying = [
            (cfg, ids) for cfg, ids in config_to_ids.items()
            if len(ids) >= MIN_EVIDENCE_SESSIONS
        ]

        if not qualifying:
            return self._insufficient_fact()

        qualifying.sort(key=lambda item: len(item[1]), reverse=True)
        top_cfg, top_ids = qualifying[0]

        return ProfileFact(
            value=top_cfg,
            evidence_session_ids=top_ids,
            confidence=0.95,
            status="determined"
        )

    # 4. Preferred Session Duration
    def _analyze_preferred_session_duration(self, sessions: List[Session]) -> ProfileFact:
        durations = []
        for s in sessions:
            dur = None
            if isinstance(s.duration, (int, float)):
                dur = int(s.duration)
            elif isinstance(s.duration, str):
                digits = "".join([c for c in s.duration if c.isdigit()])
                if digits:
                    dur = int(digits)

            if dur is not None:
                sid = str(s.session_id or s.id or "")
                durations.append((dur, sid, s.kd_ratio))

        if len(durations) < MIN_EVIDENCE_SESSIONS:
            return self._insufficient_fact()

        # Check sessions under 90 minutes vs over 90 minutes
        under_90 = [item for item in durations if item[0] < 90]
        if len(under_90) >= MIN_EVIDENCE_SESSIONS:
            avg_mins = int(round(sum(item[0] for item in under_90) / len(under_90)))
            evidence_ids = [item[1] for item in under_90]
            return ProfileFact(
                value=f"Sessions under 90 minutes (~{avg_mins} minutes average)",
                evidence_session_ids=evidence_ids,
                confidence=0.88,
                status="determined"
            )

        return self._insufficient_fact()

    # 5. Recurring Strengths
    def _analyze_recurring_strengths(
        self,
        sessions: List[Session],
        memories: Optional[List[Dict[str, Any]]] = None
    ) -> ProfileFact:
        strengths_evidence: Dict[str, List[str]] = {
            "High combat conversion (K/D >= 1.5)": [],
            "Dominant match victory execution": [],
            "High survivability (< 10 deaths)": [],
            "Effective site defense & mechanical consistency": []
        }

        for s in sessions:
            sid = str(s.session_id or s.id or "")
            if s.kd_ratio is not None and s.kd_ratio >= 1.5:
                strengths_evidence["High combat conversion (K/D >= 1.5)"].append(sid)

            if s.result and s.result.lower().startswith("win"):
                strengths_evidence["Dominant match victory execution"].append(sid)

            if s.deaths is not None and s.deaths < 10:
                strengths_evidence["High survivability (< 10 deaths)"].append(sid)

            notes = (s.player_notes or "").lower()
            if "crosshair" in notes or "defense" in notes or "locked in" in notes or "clutch" in notes:
                strengths_evidence["Effective site defense & mechanical consistency"].append(sid)

        # Filter qualifying strengths (>= 2 sessions)
        qualifying = [
            (str_desc, ids) for str_desc, ids in strengths_evidence.items()
            if len(ids) >= MIN_EVIDENCE_SESSIONS
        ]

        if not qualifying:
            return self._insufficient_fact()

        qualifying.sort(key=lambda item: len(item[1]), reverse=True)
        top_strength, ids = qualifying[0]

        return ProfileFact(
            value=top_strength,
            evidence_session_ids=ids,
            confidence=0.92,
            status="determined"
        )

    # 6. Recurring Improvement Areas
    def _analyze_recurring_improvement_areas(
        self,
        sessions: List[Session],
        memories: Optional[List[Dict[str, Any]]] = None
    ) -> ProfileFact:
        flaws_evidence: Dict[str, List[str]] = {
            "Sub-1.0 K/D combat conversion duels": [],
            "Struggles with close match conversion defeats": [],
            "High death count (> 12 deaths) from aggressive dry-peeking": [],
            "Tilt and fatigue during extended gameplay": []
        }

        for s in sessions:
            sid = str(s.session_id or s.id or "")
            if s.kd_ratio is not None and s.kd_ratio < 1.0:
                flaws_evidence["Sub-1.0 K/D combat conversion duels"].append(sid)

            if s.result and ("loss" in s.result.lower() or "defeat" in s.result.lower()):
                flaws_evidence["Struggles with close match conversion defeats"].append(sid)

            if s.deaths is not None and s.deaths > 12:
                flaws_evidence["High death count (> 12 deaths) from aggressive dry-peeking"].append(sid)

            notes = (s.player_notes or "").lower()
            if "tilt" in notes or "frustrat" in notes or "fatigue" in notes or "tired" in notes:
                flaws_evidence["Tilt and fatigue during extended gameplay"].append(sid)

        qualifying = [
            (flaw_desc, ids) for flaw_desc, ids in flaws_evidence.items()
            if len(ids) >= MIN_EVIDENCE_SESSIONS
        ]

        if not qualifying:
            return self._insufficient_fact()

        qualifying.sort(key=lambda item: len(item[1]), reverse=True)
        top_flaw, ids = qualifying[0]

        return ProfileFact(
            value=top_flaw,
            evidence_session_ids=ids,
            confidence=0.90,
            status="determined"
        )

    # -----------------------------------------------------------------
    # PERSISTENCE & DYNAMIC RE-CALCULATION
    # -----------------------------------------------------------------
    def update_profile_from_sessions(self) -> PlayerProfile:
        """
        Re-evaluates all stored sessions and updates player_profile table.
        """
        sessions = self.storage.get_recent_sessions(limit=100)
        profile = self.build_profile(sessions)

        # Store each dimension into player_profile table
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            dimensions = [
                ("preferred_game", profile.preferred_game, "gameplay"),
                ("frequently_played_maps", profile.frequently_played_maps, "maps"),
                ("frequently_used_configurations", profile.frequently_used_configurations, "loadout"),
                ("preferred_session_duration", profile.preferred_session_duration, "timing"),
                ("recurring_strengths", profile.recurring_strengths, "strengths"),
                ("recurring_improvement_areas", profile.recurring_improvement_areas, "weaknesses")
            ]

            for key, fact, category in dimensions:
                evidence_payload = {
                    "evidence_session_ids": fact.evidence_session_ids,
                    "confidence": fact.confidence,
                    "status": fact.status
                }
                cursor.execute("""
                INSERT INTO player_profile (profile_key, profile_value, category, evidence_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_key) DO UPDATE SET
                    profile_value = excluded.profile_value,
                    category = excluded.category,
                    evidence_json = excluded.evidence_json,
                    updated_at = CURRENT_TIMESTAMP
                """, (key, fact.value, category, json.dumps(evidence_payload)))

            conn.commit()
        finally:
            conn.close()

        return profile

    def get_profile(self) -> PlayerProfile:
        """Retrieves or recalculates the current player profile."""
        return self.update_profile_from_sessions()


# Default singleton instance
default_player_profile_manager = PlayerProfileManager()
