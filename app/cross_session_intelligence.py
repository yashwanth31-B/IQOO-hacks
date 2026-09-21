import math
import sqlite3
from typing import List, Dict, Any, Optional, Union, Tuple
from collections import defaultdict

from app.models import Session, CrossSessionIntelligenceResponse
from app.session_storage import SessionStorage, default_session_storage


NOT_ENOUGH_DATA = "Not enough data to determine this."
MIN_SESSIONS_REQUIRED = 2


# =====================================================================
# PHASE 11: OPTIMIZED SESSION RETRIEVER
# =====================================================================

class OptimizedSessionRetriever:
    """
    Optimized Retrieval Layer for Cross-Session Intelligence.
    
    Guarantees that the analytical engine does NOT receive the player's
    entire match history unnecessarily:
    1. Projects only the specific columns needed for each question.
    2. Applies targeted SQL filters (WHERE conditions).
    3. Restricts row fetching using targeted SQL LIMIT clauses.
    4. Records retrieval footprint metadata (retrieved count vs total count).
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage

    def get_total_count(self) -> int:
        return self.storage.count_sessions()

    def _execute_query(
        self,
        query: str,
        params: Tuple[Any, ...] = (),
        projected_fields: Optional[List[str]] = None,
        query_type: str = "custom"
    ) -> Tuple[List[Session], Dict[str, Any]]:
        conn = self.storage._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            sessions = [self.storage._row_to_session(r) for r in rows]
            total_count = self.get_total_count()
            metadata = {
                "total_stored_sessions": total_count,
                "retrieved_session_count": len(sessions),
                "query_type": query_type,
                "fields_projected": projected_fields or ["minimal_performance_columns"],
                "retrieval_optimized": True
            }
            return sessions, metadata
        finally:
            conn.close()

    def retrieve_top_performing_sessions(
        self,
        game: Optional[str] = None,
        limit: int = 5,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves top-performing sessions by K/D ratio without pulling full history."""
        if sessions is not None:
            filtered = [s for s in sessions if s.kd_ratio is not None and (game is None or s.game == game)]
            sorted_s = sorted(filtered, key=lambda s: s.kd_ratio or 0.0, reverse=True)[:limit]
            return sorted_s, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(sorted_s),
                "query_type": "in_memory_top_performing",
                "fields_projected": ["session_id", "game", "map", "configuration", "kd_ratio", "kills", "deaths", "started_at"],
                "retrieval_optimized": True
            }

        fields = [
            "id", "session_id", "game", "map", "configuration",
            "started_at", "duration", "score", "kills", "deaths", "assists", "kd_ratio", "result", "player_notes"
        ]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL AND game = ? ORDER BY kd_ratio DESC, id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL ORDER BY kd_ratio DESC, id DESC LIMIT ?"
            params = (limit,)

        return self._execute_query(sql, params, fields, query_type="top_performing_sessions")

    def retrieve_best_and_worst_sessions(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves boundary sessions (top 2 and lowest 2) to analyze what changed."""
        if sessions is not None:
            filtered = [s for s in sessions if s.kd_ratio is not None and (game is None or s.game == game)]
            if len(filtered) < 2:
                return filtered, {
                    "total_stored_sessions": len(sessions),
                    "retrieved_session_count": len(filtered),
                    "query_type": "in_memory_best_worst",
                    "retrieval_optimized": True
                }
            sorted_s = sorted(filtered, key=lambda s: s.kd_ratio or 0.0, reverse=True)
            result = [sorted_s[0], sorted_s[-1]]
            return result, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(result),
                "query_type": "in_memory_best_worst",
                "fields_projected": ["session_id", "game", "map", "configuration", "kd_ratio", "kills", "deaths", "duration"],
                "retrieval_optimized": True
            }

        fields = [
            "id", "session_id", "game", "map", "configuration",
            "started_at", "duration", "score", "kills", "deaths", "assists", "kd_ratio", "result"
        ]
        cols_sql = ", ".join(fields)
        conn = self.storage._get_connection()
        try:
            cursor = conn.cursor()
            if game:
                cursor.execute(f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL AND game = ? ORDER BY kd_ratio DESC, id DESC LIMIT 1", (game,))
                best_row = cursor.fetchone()
                cursor.execute(f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL AND game = ? ORDER BY kd_ratio ASC, id ASC LIMIT 1", (game,))
                worst_row = cursor.fetchone()
            else:
                cursor.execute(f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL ORDER BY kd_ratio DESC, id DESC LIMIT 1")
                best_row = cursor.fetchone()
                cursor.execute(f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL ORDER BY kd_ratio ASC, id ASC LIMIT 1")
                worst_row = cursor.fetchone()

            retrieved = []
            if best_row:
                retrieved.append(self.storage._row_to_session(best_row))
            if worst_row and (not best_row or worst_row["id"] != best_row["id"]):
                retrieved.append(self.storage._row_to_session(worst_row))

            metadata = {
                "total_stored_sessions": self.get_total_count(),
                "retrieved_session_count": len(retrieved),
                "query_type": "boundary_comparison_best_worst",
                "fields_projected": fields,
                "retrieval_optimized": True
            }
            return retrieved, metadata
        finally:
            conn.close()

    def retrieve_chronological_window(
        self,
        game: Optional[str] = None,
        limit: int = 15,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves a bounded recent window of sessions ordered oldest to newest."""
        if sessions is not None:
            filtered = [s for s in sessions if s.kd_ratio is not None and (game is None or s.game == game)]
            window = filtered[-limit:] if len(filtered) > limit else filtered
            return window, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(window),
                "query_type": "in_memory_chronological_window",
                "fields_projected": ["session_id", "started_at", "kd_ratio", "kills", "deaths", "duration"],
                "retrieval_optimized": True
            }

        fields = [
            "id", "session_id", "game", "map", "configuration",
            "started_at", "duration", "score", "kills", "deaths", "assists", "kd_ratio", "result"
        ]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL AND game = ? ORDER BY id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE kd_ratio IS NOT NULL ORDER BY id DESC LIMIT ?"
            params = (limit,)

        retrieved, meta = self._execute_query(sql, params, fields, query_type="chronological_window")
        # Reverse to chronological order (oldest to newest)
        return list(reversed(retrieved)), meta

    def retrieve_map_sessions(
        self,
        game: Optional[str] = None,
        limit: int = 50,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves sessions with recorded map data."""
        if sessions is not None:
            filtered = [s for s in sessions if s.map and s.kd_ratio is not None and (game is None or s.game == game)][:limit]
            return filtered, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(filtered),
                "query_type": "in_memory_map_sessions",
                "fields_projected": ["session_id", "map", "kd_ratio", "result", "kills", "deaths"],
                "retrieval_optimized": True
            }

        fields = ["id", "session_id", "game", "map", "kd_ratio", "result", "kills", "deaths", "duration"]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE map IS NOT NULL AND TRIM(map) != '' AND kd_ratio IS NOT NULL AND game = ? ORDER BY id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE map IS NOT NULL AND TRIM(map) != '' AND kd_ratio IS NOT NULL ORDER BY id DESC LIMIT ?"
            params = (limit,)

        return self._execute_query(sql, params, fields, query_type="map_sessions")

    def retrieve_configuration_sessions(
        self,
        game: Optional[str] = None,
        limit: int = 50,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves sessions with recorded configuration data."""
        def has_cfg(s: Session) -> bool:
            if isinstance(s.configuration, dict):
                return bool(s.configuration.get("primary_weapon") or s.configuration.get("weapon") or s.configuration)
            return bool(s.configuration and str(s.configuration).strip())

        if sessions is not None:
            filtered = [s for s in sessions if has_cfg(s) and s.kd_ratio is not None and (game is None or s.game == game)][:limit]
            return filtered, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(filtered),
                "query_type": "in_memory_configuration_sessions",
                "fields_projected": ["session_id", "configuration", "kd_ratio", "result", "kills", "deaths"],
                "retrieval_optimized": True
            }

        fields = ["id", "session_id", "game", "configuration", "kd_ratio", "result", "kills", "deaths"]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE configuration IS NOT NULL AND TRIM(configuration) != '' AND kd_ratio IS NOT NULL AND game = ? ORDER BY id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE configuration IS NOT NULL AND TRIM(configuration) != '' AND kd_ratio IS NOT NULL ORDER BY id DESC LIMIT ?"
            params = (limit,)

        return self._execute_query(sql, params, fields, query_type="configuration_sessions")

    def retrieve_duration_sessions(
        self,
        game: Optional[str] = None,
        limit: int = 20,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves sessions with recorded duration and K/D."""
        if sessions is not None:
            filtered = [s for s in sessions if s.duration is not None and s.kd_ratio is not None and (game is None or s.game == game)]
            sorted_s = sorted(filtered, key=lambda s: s.kd_ratio or 0.0, reverse=True)[:limit]
            return sorted_s, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(sorted_s),
                "query_type": "in_memory_duration_sessions",
                "fields_projected": ["session_id", "duration", "kd_ratio", "kills", "deaths"],
                "retrieval_optimized": True
            }

        fields = ["id", "session_id", "game", "map", "duration", "kd_ratio", "kills", "deaths", "result"]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE duration IS NOT NULL AND kd_ratio IS NOT NULL AND game = ? ORDER BY kd_ratio DESC, id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE duration IS NOT NULL AND kd_ratio IS NOT NULL ORDER BY kd_ratio DESC, id DESC LIMIT ?"
            params = (limit,)

        return self._execute_query(sql, params, fields, query_type="duration_sessions")

    def retrieve_mistake_sessions(
        self,
        game: Optional[str] = None,
        limit: int = 25,
        sessions: Optional[List[Session]] = None
    ) -> Tuple[List[Session], Dict[str, Any]]:
        """Retrieves sessions recording deaths or mistake-related player notes."""
        if sessions is not None:
            filtered = [
                s for s in sessions
                if ((s.deaths is not None and s.deaths > 0) or s.player_notes) and (game is None or s.game == game)
            ][:limit]
            return filtered, {
                "total_stored_sessions": len(sessions),
                "retrieved_session_count": len(filtered),
                "query_type": "in_memory_mistake_sessions",
                "fields_projected": ["session_id", "deaths", "kills", "kd_ratio", "duration", "player_notes", "performance_metrics"],
                "retrieval_optimized": True
            }

        fields = [
            "id", "session_id", "game", "map", "duration", "kills", "deaths",
            "kd_ratio", "result", "player_notes", "performance_metrics_json"
        ]
        cols_sql = ", ".join(fields)
        if game:
            sql = f"SELECT {cols_sql} FROM sessions WHERE ((deaths IS NOT NULL AND deaths > 0) OR (player_notes IS NOT NULL AND TRIM(player_notes) != '')) AND game = ? ORDER BY deaths DESC, id DESC LIMIT ?"
            params = (game, limit)
        else:
            sql = f"SELECT {cols_sql} FROM sessions WHERE (deaths IS NOT NULL AND deaths > 0) OR (player_notes IS NOT NULL AND TRIM(player_notes) != '') ORDER BY deaths DESC, id DESC LIMIT ?"
            params = (limit,)

        return self._execute_query(sql, params, fields, query_type="mistake_sessions")


# =====================================================================
# PHASE 11: CROSS-SESSION INTELLIGENCE ENGINE
# =====================================================================

class CrossSessionIntelligenceEngine:
    """
    Cross-Session Intelligence Engine (Phase 11).
    
    Synthesizes historical gaming sessions into actionable intelligence.
    Enforces all core constraints:
    - Answers support questions:
        1. When did I perform best?
        2. What changed?
        3. Am I improving?
        4. Which map has my strongest recorded performance?
        5. Which configuration has better recorded results?
        6. How long are my strongest sessions?
        7. What mistakes keep repeating?
        8. What am I improving?
    - Explicit four-part structure:
        ANSWER
        EVIDENCE
        INSIGHT
        RECOMMENDATION
    - Every answer references stored sessions.
    - Does not invent statistics.
    - Does not infer causation without evidence.
    - If insufficient data: "Not enough data to determine this."
    - Uses OptimizedSessionRetriever so the AI does not receive entire match history.
    """

    def __init__(
        self,
        storage: Optional[SessionStorage] = None,
        retriever: Optional[OptimizedSessionRetriever] = None
    ):
        self.storage = storage or default_session_storage
        self.retriever = retriever or OptimizedSessionRetriever(self.storage)

    def _insufficient_response(
        self,
        question: str,
        analysis_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CrossSessionIntelligenceResponse:
        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=NOT_ENOUGH_DATA,
            evidence=[],
            insight=NOT_ENOUGH_DATA,
            recommendation="Record more gameplay sessions with complete match data to enable cross-session analysis.",
            evidence_session_ids=[],
            status="insufficient_data",
            metrics_summary={},
            retrieval_metadata=metadata or {}
        )

    def _fmt_cfg(self, s: Session) -> str:
        if isinstance(s.configuration, dict):
            w = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
            return f"{w} configuration" if w else "Custom loadout"
        if s.configuration:
            return str(s.configuration).strip()
        return "Unspecified configuration"

    def _extract_mins(self, s: Session) -> Optional[int]:
        if isinstance(s.duration, (int, float)):
            return int(s.duration)
        if isinstance(s.duration, str):
            digits = "".join([c for c in s.duration if c.isdigit()])
            if digits:
                return int(digits)
        return None

    # -----------------------------------------------------------------
    # QUESTION 1: "When did I perform best?"
    # -----------------------------------------------------------------
    def when_did_i_perform_best(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "When did I perform best?"
        analysis_type = "when_did_i_perform_best"

        retrieved, meta = self.retriever.retrieve_top_performing_sessions(game=game, limit=5, sessions=sessions)
        valid = [s for s in retrieved if s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        best = valid[0]
        best_sid = str(best.session_id or best.id)
        best_cfg = self._fmt_cfg(best)
        best_time = best.started_at or best.ended_at or f"Session #{best_sid}"
        best_map = best.map or "Unspecified map"
        best_game = best.game or "Unspecified game"

        # Check runner up
        runner = valid[1]
        runner_sid = str(runner.session_id or runner.id)
        runner_time = runner.started_at or f"Session #{runner_sid}"

        answer = (
            f"Your best recorded performance occurred on {best_time} in Session #{best_sid} "
            f"playing {best_game} on {best_map}, achieving your peak K/D of {best.kd_ratio:.2f} "
            f"({best.kills or 0} kills, {best.deaths or 0} deaths)."
        )

        evidence = [
            f"Session #{best_sid} ({best_time}): K/D {best.kd_ratio:.2f} ({best.kills or 0} kills, {best.deaths or 0} deaths), "
            f"map: {best_map}, configuration: {best_cfg}, duration: {best.duration or 'N/A'} mins, result: {best.result or 'N/A'}.",
            f"Session #{runner_sid} ({runner_time}): K/D {runner.kd_ratio:.2f} ({runner.kills or 0} kills, {runner.deaths or 0} deaths), "
            f"map: {runner.map or 'N/A'}, configuration: {self._fmt_cfg(runner)}."
        ]

        insight = (
            f"Your peak combat efficiency in Session #{best_sid} coincided with {best_cfg} on {best_map}. "
            "While these recorded parameters accompanied your highest output, the telemetry demonstrates statistical "
            "correlation rather than confirmed causation, as lobby matchmaking brackets and teammate contributions were unmeasured."
        )

        recommendation = (
            f"Review the engagement timing and positioning recorded in Session #{best_sid} as an evidence-based "
            f"benchmark for future matches on {best_map}."
        )

        evidence_sids = [best_sid, runner_sid]

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=evidence_sids,
            status="answered",
            metrics_summary={
                "best_session_id": best_sid,
                "best_kd": best.kd_ratio,
                "best_kills": best.kills,
                "best_deaths": best.deaths,
                "best_time": best_time,
                "best_map": best_map
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 2: "What changed?"
    # -----------------------------------------------------------------
    def what_changed(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "What changed?"
        analysis_type = "what_changed"

        retrieved, meta = self.retriever.retrieve_best_and_worst_sessions(game=game, sessions=sessions)
        valid = [s for s in retrieved if s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        best = valid[0]
        worst = valid[-1]
        best_sid = str(best.session_id or best.id)
        worst_sid = str(worst.session_id or worst.id)

        if best_sid == worst_sid:
            return self._insufficient_response(question, analysis_type, meta)

        best_cfg = self._fmt_cfg(best)
        worst_cfg = self._fmt_cfg(worst)
        kd_delta = best.kd_ratio - worst.kd_ratio

        changes = []
        if best.map != worst.map:
            changes.append(f"map environment ({best.map or 'N/A'} vs {worst.map or 'N/A'})")
        if best_cfg != worst_cfg:
            changes.append(f"loadout ({best_cfg} vs {worst_cfg})")
        if best.duration != worst.duration and best.duration is not None and worst.duration is not None:
            changes.append(f"duration ({best.duration} vs {worst.duration} mins)")
        changes.append(f"combat trade efficiency ({kd_delta:+.2f} K/D)")

        answer = (
            f"Comparing your best performance in Session #{best_sid} (K/D {best.kd_ratio:.2f}) against your lowest in "
            f"Session #{worst_sid} (K/D {worst.kd_ratio:.2f}), the key recorded differences were "
            f"{', '.join(changes)}."
        )

        evidence = [
            f"Session #{best_sid} (Peak): K/D = {best.kd_ratio:.2f} ({best.kills or 0} kills, {best.deaths or 0} deaths), "
            f"map: {best.map or 'Unspecified'}, config: {best_cfg}, duration: {best.duration or 'N/A'} mins, result: {best.result or 'N/A'}.",
            f"Session #{worst_sid} (Lowest): K/D = {worst.kd_ratio:.2f} ({worst.kills or 0} kills, {worst.deaths or 0} deaths), "
            f"map: {worst.map or 'Unspecified'}, config: {worst_cfg}, duration: {worst.duration or 'N/A'} mins, result: {worst.result or 'N/A'}."
        ]

        insight = (
            f"Performance shifts correlate with changes in map environment ({best.map} vs {worst.map}) and configuration "
            f"({best_cfg} vs {worst_cfg}). However, the telemetry does not prove these variables alone caused the divergence, "
            "as opponent skill, team composition, and match pacing also differed across sessions."
        )

        recommendation = (
            f"Maintain the loadout and engagement pacing demonstrated in Session #{best_sid} when deploying into "
            f"{worst.map or 'lower-performing environments'}."
        )

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=[best_sid, worst_sid],
            status="answered",
            metrics_summary={
                "best_session_id": best_sid,
                "best_kd": best.kd_ratio,
                "worst_session_id": worst_sid,
                "worst_kd": worst.kd_ratio,
                "kd_delta": round(kd_delta, 2),
                "best_map": best.map,
                "worst_map": worst.map,
                "best_config": best_cfg,
                "worst_config": worst_cfg
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 3: "Am I improving?"
    # -----------------------------------------------------------------
    def am_i_improving(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "Am I improving?"
        analysis_type = "am_i_improving"

        retrieved, meta = self.retriever.retrieve_chronological_window(game=game, limit=15, sessions=sessions)
        valid = [s for s in retrieved if s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        kds = [s.kd_ratio for s in valid]
        sids = [str(s.session_id or s.id) for s in valid]
        n = len(kds)

        mean_kd = sum(kds) / n
        variance = sum((x - mean_kd) ** 2 for x in kds) / n
        std_dev = math.sqrt(variance)

        mid = n // 2
        early_half = kds[:mid]
        recent_half = kds[mid:]
        early_avg = sum(early_half) / len(early_half)
        recent_avg = sum(recent_half) / len(recent_half)
        delta = recent_avg - early_avg

        diffs = [kds[i+1] - kds[i] for i in range(n-1)]
        sign_changes = sum(1 for i in range(len(diffs)-1) if (diffs[i] > 0 and diffs[i+1] < 0) or (diffs[i] < 0 and diffs[i+1] > 0))
        is_oscillating = sign_changes >= 2 and std_dev >= 0.35

        evidence = [f"Session #{sids[i]}: K/D = {kds[i]:.2f} ({valid[i].kills or 0} kills, {valid[i].deaths or 0} deaths)" for i in range(n)]

        if is_oscillating:
            trend = "inconsistent"
            answer = (
                f"Your recorded performance shows high volatility rather than a steady trajectory, "
                f"with K/D fluctuating between {min(kds):.2f} and {max(kds):.2f} across {n} recorded sessions."
            )
            insight = (
                f"Performance across recent matches exhibits swings (standard deviation {std_dev:.2f}). "
                "While this reflects varied match outputs, the data does not isolate specific causes such as opponent rank or lobby variance."
            )
            recommendation = "Standardize pre-match warmups to stabilize combat consistency and reduce volatility between games."
        elif delta > 0.15:
            trend = "improving"
            answer = (
                f"Yes, your recorded performance indicates an upward trajectory, with average K/D improving from "
                f"{early_avg:.2f} in earlier matches to {recent_avg:.2f} in recent matches (net gain of {delta:+.2f} K/D across {n} sessions)."
            )
            insight = (
                "Combat conversion exhibits a verifiable improving trend across recorded matches. "
                "However, while statistics show higher combat efficiency, external variables such as matchmaking brackets were unobserved."
            )
            recommendation = "Maintain current practice routines and warmup habits to reinforce this upward combat momentum."
        elif delta < -0.15:
            trend = "declining"
            answer = (
                f"No, your recorded performance indicates a downward trajectory, with average K/D declining from "
                f"{early_avg:.2f} in earlier matches to {recent_avg:.2f} in recent matches (net drop of {delta:+.2f} K/D across {n} sessions)."
            )
            insight = (
                "The data establishes a statistical drop in combat output. However, it does not prove that mechanical skill deteriorated, "
                "as opponent skill and tactical changes also varied."
            )
            recommendation = "Review early engagement replays from recent matches to identify whether positioning fatigue is impacting trades."
        else:
            trend = "consistent"
            answer = (
                f"Your recorded performance has remained steady across matches, maintaining an average K/D of "
                f"~{mean_kd:.2f} across {n} recorded sessions (net delta of {delta:+.2f})."
            )
            insight = (
                f"Combat efficiency has stayed stable with minimal deviation (standard deviation {std_dev:.2f}). "
                "Performance is consistent within current competition levels."
            )
            recommendation = "Introduce deliberate tactical drills to break through the current performance plateau."

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=sids,
            status="answered",
            metrics_summary={
                "trend": trend,
                "session_count": n,
                "mean_kd": round(mean_kd, 2),
                "early_avg_kd": round(early_avg, 2),
                "recent_avg_kd": round(recent_avg, 2),
                "delta": round(delta, 2),
                "std_dev": round(std_dev, 2)
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 4: "Which map has my strongest recorded performance?"
    # -----------------------------------------------------------------
    def which_map_strongest(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "Which map has my strongest recorded performance?"
        analysis_type = "which_map_strongest"

        retrieved, meta = self.retriever.retrieve_map_sessions(game=game, limit=50, sessions=sessions)
        valid = [s for s in retrieved if s.map and s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        map_groups: Dict[str, List[Session]] = defaultdict(list)
        for s in valid:
            map_groups[s.map].append(s)

        map_stats = []
        evidence = []
        all_sids = []

        for map_name, s_list in map_groups.items():
            sids = [str(s.session_id or s.id) for s in s_list]
            all_sids.extend(sids)
            kd_vals = [s.kd_ratio for s in s_list]
            avg_kd = sum(kd_vals) / len(kd_vals)
            wins = sum(1 for s in s_list if s.result and s.result.lower().startswith("win"))
            win_pct = (wins / len(s_list)) * 100
            evidence.append(
                f"{map_name}: average K/D {avg_kd:.2f}, {win_pct:.0f}% win rate across {len(s_list)} session{'s' if len(s_list) > 1 else ''} "
                f"({', '.join('Session #' + sid for sid in sids)})."
            )
            map_stats.append({
                "map": map_name,
                "avg_kd": avg_kd,
                "win_pct": win_pct,
                "count": len(s_list),
                "sids": sids
            })

        map_stats.sort(key=lambda x: (x["avg_kd"], x["count"]), reverse=True)
        top = map_stats[0]

        other_desc = ", ".join(f"{m['map']} ({m['avg_kd']:.2f} K/D)" for m in map_stats[1:])
        comp_clause = f", outperforming {other_desc}" if other_desc else ""

        answer = (
            f"Your strongest recorded performance is on {top['map']}, where you achieved an average K/D of "
            f"{top['avg_kd']:.2f} with a {top['win_pct']:.0f}% win rate across {top['count']} recorded session{'s' if top['count'] > 1 else ''}{comp_clause}."
        )

        insight = (
            f"{top['map']} yielded your highest combat efficiency across recorded matches. "
            "While comfort and positioning on this map correlate with higher combat conversion, the data does not establish "
            "map layout as the sole cause of performance differences, as opponent ranks and lobby pacing were unobserved."
        )

        recommendation = (
            f"Apply the crosshair placement and rotation timing that succeeded on {top['map']} to secondary maps where efficiency was lower."
        )

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=all_sids,
            status="answered",
            metrics_summary={
                "strongest_map": top["map"],
                "strongest_map_avg_kd": round(top["avg_kd"], 2),
                "strongest_map_sessions": top["count"],
                "total_maps_compared": len(map_stats)
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 5: "Which configuration has better recorded results?"
    # -----------------------------------------------------------------
    def which_configuration_better(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "Which configuration has better recorded results?"
        analysis_type = "which_configuration_better"

        retrieved, meta = self.retriever.retrieve_configuration_sessions(game=game, limit=50, sessions=sessions)
        valid = [s for s in retrieved if self._fmt_cfg(s) != "Unspecified configuration" and s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        cfg_groups: Dict[str, List[Session]] = defaultdict(list)
        for s in valid:
            cfg_groups[self._fmt_cfg(s)].append(s)

        cfg_stats = []
        evidence = []
        all_sids = []

        for cfg_name, s_list in cfg_groups.items():
            sids = [str(s.session_id or s.id) for s in s_list]
            all_sids.extend(sids)
            kd_vals = [s.kd_ratio for s in s_list]
            avg_kd = sum(kd_vals) / len(kd_vals)
            wins = sum(1 for s in s_list if s.result and s.result.lower().startswith("win"))
            win_pct = (wins / len(s_list)) * 100
            evidence.append(
                f"{cfg_name}: average K/D {avg_kd:.2f}, {win_pct:.0f}% win rate across {len(s_list)} session{'s' if len(s_list) > 1 else ''} "
                f"({', '.join('Session #' + sid for sid in sids)})."
            )
            cfg_stats.append({
                "config": cfg_name,
                "avg_kd": avg_kd,
                "win_pct": win_pct,
                "count": len(s_list),
                "sids": sids
            })

        cfg_stats.sort(key=lambda x: (x["avg_kd"], x["count"]), reverse=True)
        top = cfg_stats[0]

        other_desc = ", ".join(f"{c['config']} ({c['avg_kd']:.2f} K/D)" for c in cfg_stats[1:])
        comp_clause = f", higher than {other_desc}" if other_desc else ""

        answer = (
            f"Your best recorded configuration is {top['config']}, recording the highest average K/D of "
            f"{top['avg_kd']:.2f} across {top['count']} session{'s' if top['count'] > 1 else ''}{comp_clause}."
        )

        insight = (
            f"Sessions using {top['config']} correlate with higher combat conversion in recorded matches. "
            "However, telemetry does not prove that the loadout itself caused superior performance, "
            "as engagement distances, team synergy, and player alertness also varied across sessions."
        )

        recommendation = (
            f"Prioritize {top['config']} in primary competitive matches while isolating secondary loadouts for controlled practice."
        )

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=all_sids,
            status="answered",
            metrics_summary={
                "best_configuration": top["config"],
                "best_config_avg_kd": round(top["avg_kd"], 2),
                "best_config_sessions": top["count"],
                "total_configs_compared": len(cfg_stats)
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 6: "How long are my strongest sessions?"
    # -----------------------------------------------------------------
    def how_long_strongest_sessions(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "How long are my strongest sessions?"
        analysis_type = "how_long_strongest_sessions"

        retrieved, meta = self.retriever.retrieve_duration_sessions(game=game, limit=10, sessions=sessions)
        valid = []
        for s in retrieved:
            mins = self._extract_mins(s)
            if mins is not None and s.kd_ratio is not None:
                valid.append((s, mins))

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        # Sort by K/D descending to isolate strongest sessions
        valid.sort(key=lambda x: x[0].kd_ratio, reverse=True)
        # Select top performing sessions (up to top 5)
        top_slice = valid[:min(5, len(valid))]
        durations = [m for _, m in top_slice]
        avg_mins = int(round(sum(durations) / len(durations)))
        min_mins = min(durations)
        max_mins = max(durations)

        evidence = [
            f"Session #{s.session_id or s.id}: duration = {m} mins, K/D = {s.kd_ratio:.2f} ({s.kills or 0} kills, {s.deaths or 0} deaths)"
            for s, m in top_slice
        ]
        sids = [str(s.session_id or s.id) for s, _ in top_slice]

        answer = (
            f"Your strongest recorded sessions average {avg_mins} minutes in duration "
            f"(ranging from {min_mins} to {max_mins} minutes across your top-performing matches)."
        )

        insight = (
            f"Your highest combat efficiency clusters in matches lasting approximately {avg_mins} minutes. "
            "While this correlation suggests peak alertness during this duration bracket, the data reflects statistical "
            "correlation rather than definitive fatigue causation, as match pacing was not controlled."
        )

        recommendation = (
            f"Structure competitive play blocks around ~{avg_mins} minutes to align with your highest recorded efficiency window."
        )

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=sids,
            status="answered",
            metrics_summary={
                "average_duration_minutes": avg_mins,
                "min_duration_minutes": min_mins,
                "max_duration_minutes": max_mins,
                "strongest_sessions_evaluated": len(top_slice)
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 7: "What mistakes keep repeating?"
    # -----------------------------------------------------------------
    def what_mistakes_repeating(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "What mistakes keep repeating?"
        analysis_type = "what_mistakes_repeating"

        retrieved, meta = self.retriever.retrieve_mistake_sessions(game=game, limit=25, sessions=sessions)
        valid = [s for s in retrieved if (s.deaths is not None and s.deaths > 0) or s.player_notes]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        # Inspect notes for recurring themes (e.g. open field, crossfire, rotation, choke point, positioning, reload, greed)
        themes = ["crossfire", "open field", "positioning", "choke point", "rotation", "isolated", "overextend", "rush"]
        matched_sessions_by_theme: Dict[str, List[Session]] = defaultdict(list)

        for s in valid:
            notes = (s.player_notes or "").lower()
            for theme in themes:
                if theme in notes:
                    matched_sessions_by_theme[theme].append(s)

        # Find theme with >= 2 sessions
        identified_theme = None
        for theme, s_list in matched_sessions_by_theme.items():
            if len(s_list) >= 2:
                identified_theme = (theme, s_list)
                break

        if identified_theme:
            theme_name, matched_s = identified_theme
            sids = [str(s.session_id or s.id) for s in matched_s]
            answer = (
                f"The primary repeating mistake identified across recorded sessions is repeated {theme_name} compromises "
                f"(recorded across {len(matched_s)} sessions)."
            )
            evidence = [
                f"Session #{s.session_id or s.id}: {s.deaths or 0} deaths, duration {s.duration or 'N/A'} mins (note: '{s.player_notes}')."
                for s in matched_s
            ]
            insight = (
                f"Repeated eliminations occurred under similar {theme_name} conditions across multiple matches. "
                "The telemetry establishes recurrence of these recorded outcomes, but does not identify unrecorded factors "
                "such as enemy communication or tactical flanks."
            )
            recommendation = (
                f"Prioritize defensive spacing and adjust rotation protocols to avoid recurring {theme_name} exposure."
            )
        else:
            # Look for repeated high deaths / negative trades across sessions
            negative_trade_sessions = [s for s in valid if s.deaths is not None and s.kills is not None and s.deaths > s.kills]
            if len(negative_trade_sessions) >= 2:
                sids = [str(s.session_id or s.id) for s in negative_trade_sessions[:4]]
                answer = (
                    f"The primary repeating mistake identified across recorded sessions is unfavorable combat trading "
                    f"resulting in higher deaths than kills (observed across {len(negative_trade_sessions)} sessions)."
                )
                evidence = [
                    f"Session #{s.session_id or s.id}: {s.deaths} deaths vs {s.kills} kills (K/D {s.kd_ratio:.2f})."
                    for s in negative_trade_sessions[:4]
                ]
                insight = (
                    "Consecutive matches recorded unfavorable death-to-kill trades. The data confirms recurring losses in "
                    "direct combat engagements without proving specific aiming or hardware defects."
                )
                recommendation = "Disengage from 50/50 duels when lacking positional or health advantages."
            else:
                high_death_sessions = [s for s in valid if s.deaths is not None and s.deaths >= 4]
                if len(high_death_sessions) >= 2:
                    sids = [str(s.session_id or s.id) for s in high_death_sessions[:4]]
                    answer = (
                        f"The primary repeating mistake identified across recorded sessions is elevated elimination counts "
                        f"(recorded in {len(high_death_sessions)} sessions)."
                    )
                    evidence = [
                        f"Session #{s.session_id or s.id}: {s.deaths} deaths, duration {s.duration or 'N/A'} mins."
                        for s in high_death_sessions[:4]
                    ]
                    insight = (
                        "High elimination counts recurred across multiple recorded matches. Stored data notes the frequency "
                        "of deaths without establishing enemy loadout or team spacing causes."
                    )
                    recommendation = "Adopt more conservative fallback routes when taking initial fire."
                else:
                    return self._insufficient_response(question, analysis_type, meta)

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=sids,
            status="answered",
            metrics_summary={"mistake_sessions_count": len(sids)},
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # QUESTION 8: "What am I improving?"
    # -----------------------------------------------------------------
    def what_am_i_improving(
        self,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        question = "What am I improving?"
        analysis_type = "what_am_i_improving"

        retrieved, meta = self.retriever.retrieve_chronological_window(game=game, limit=15, sessions=sessions)
        valid = [s for s in retrieved if s.kd_ratio is not None]

        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_response(question, analysis_type, meta)

        n = len(valid)
        mid = n // 2
        early = valid[:mid]
        recent = valid[mid:]

        early_sids = [str(s.session_id or s.id) for s in early]
        recent_sids = [str(s.session_id or s.id) for s in recent]
        all_sids = early_sids + recent_sids

        # Evaluate distinct metrics
        early_kd = sum(s.kd_ratio for s in early) / len(early)
        recent_kd = sum(s.kd_ratio for s in recent) / len(recent)
        delta_kd = recent_kd - early_kd

        early_kills = sum(s.kills or 0 for s in early) / len(early)
        recent_kills = sum(s.kills or 0 for s in recent) / len(recent)
        delta_kills = recent_kills - early_kills

        early_deaths = sum(s.deaths or 0 for s in early) / len(early)
        recent_deaths = sum(s.deaths or 0 for s in recent) / len(recent)
        death_reduction = early_deaths - recent_deaths

        improvements = []
        if delta_kd > 0.10:
            improvements.append(f"combat conversion (K/D gain of {delta_kd:+.2f})")
        if death_reduction > 0.5:
            improvements.append(f"survival discipline (deaths reduced by {death_reduction:.1f} per match)")
        if delta_kills > 0.5:
            improvements.append(f"offensive output (kills increased by +{delta_kills:.1f} per match)")

        evidence = [
            f"Earlier sessions ({', '.join('Session #' + sid for sid in early_sids)}): average K/D {early_kd:.2f}, "
            f"average kills {early_kills:.1f}, average deaths {early_deaths:.1f}.",
            f"Recent sessions ({', '.join('Session #' + sid for sid in recent_sids)}): average K/D {recent_kd:.2f}, "
            f"average kills {recent_kills:.1f}, average deaths {recent_deaths:.1f}."
        ]

        if improvements:
            improvements_str = " and ".join(improvements)
            answer = f"Based on your recorded history, you are showing measurable improvement in {improvements_str}."
            insight = (
                f"Recent matches confirm measurable positive progression in {improvements_str}. "
                "While the upward trajectory is supported by recorded match telemetry, lobby matchmaking tiers and teammate assists were unobserved."
            )
            recommendation = "Continue the tactical habits supporting these gains while monitoring consistency across diverse maps."
        else:
            answer = (
                f"Based on your recorded history across {n} sessions, none of the primary metrics "
                f"(K/D, survival, or kill conversion) show positive gains between earlier and recent sessions."
            )
            insight = (
                "Recent matches do not show positive statistical gains relative to earlier baselines. "
                "The data establishes current output levels without attributing causation to fatigue or opponent strength."
            )
            recommendation = "Focus on baseline fundamentals such as crosshair placement to initiate upward progress."

        return CrossSessionIntelligenceResponse(
            question=question,
            analysis_type=analysis_type,
            answer=answer,
            evidence=evidence,
            insight=insight,
            recommendation=recommendation,
            evidence_session_ids=all_sids,
            status="answered",
            metrics_summary={
                "delta_kd": round(delta_kd, 2),
                "delta_kills": round(delta_kills, 2),
                "death_reduction": round(death_reduction, 2),
                "improvements_count": len(improvements)
            },
            retrieval_metadata=meta
        )

    # -----------------------------------------------------------------
    # UNIFIED DISPATCHER
    # -----------------------------------------------------------------
    def ask(
        self,
        question: str,
        game: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionIntelligenceResponse:
        """
        Dispatches any analytical question to its targeted handler.
        """
        q = question.lower().strip()

        # 1. When did I perform best?
        if ("when" in q and any(w in q for w in ["best", "peak", "highest", "strongest"])) or "when did i perform best" in q:
            return self.when_did_i_perform_best(game=game, sessions=sessions)

        # 2. What changed?
        elif any(phrase in q for phrase in ["what changed", "what is different", "between my best and worst", "best vs worst", "best and worst"]):
            return self.what_changed(game=game, sessions=sessions)

        # 3. What am I improving? (Check before "am i improving" because "what am i improving" contains "am i improving")
        elif any(phrase in q for phrase in ["what am i improving", "what areas am i improving", "what is improving", "what have i improved"]) or ("what" in q and "improv" in q):
            return self.what_am_i_improving(game=game, sessions=sessions)

        # 4. Am I improving?
        elif any(phrase in q for phrase in ["am i improving", "am i getting better", "is my performance improving", "improvement trend", "improving?"]):
            return self.am_i_improving(game=game, sessions=sessions)

        # 5. Which map has my strongest recorded performance?
        elif "map" in q and any(w in q for w in ["strongest", "best", "highest", "top", "favorite"]):
            return self.which_map_strongest(game=game, sessions=sessions)

        # 6. Which configuration has better recorded results?
        elif any(w in q for w in ["configuration", "loadout", "setup", "weapon"]) and any(w in q for w in ["better", "best", "strongest", "higher", "top"]):
            return self.which_configuration_better(game=game, sessions=sessions)

        # 7. How long are my strongest sessions?
        elif ("how long" in q or "duration" in q or "length" in q) and any(w in q for w in ["strongest", "best", "peak"]):
            return self.how_long_strongest_sessions(game=game, sessions=sessions)

        # 8. What mistakes keep repeating?
        elif any(phrase in q for phrase in ["mistakes keep repeating", "repeating mistakes", "repeated mistakes", "recurring mistakes", "what mistakes", "bad habits", "repeating errors", "mistakes"]):
            return self.what_mistakes_repeating(game=game, sessions=sessions)

        # Intelligent fallbacks
        elif "map" in q:
            return self.which_map_strongest(game=game, sessions=sessions)
        elif "config" in q or "weapon" in q or "loadout" in q:
            return self.which_configuration_better(game=game, sessions=sessions)
        elif "duration" in q or "time" in q:
            return self.how_long_strongest_sessions(game=game, sessions=sessions)
        elif "mistake" in q or "death" in q:
            return self.what_mistakes_repeating(game=game, sessions=sessions)
        else:
            return self.am_i_improving(game=game, sessions=sessions)


# Default singleton instance
default_cross_session_intelligence = CrossSessionIntelligenceEngine()
