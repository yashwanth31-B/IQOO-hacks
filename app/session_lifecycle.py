import json
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

from app.models import Session, DetectionResult, MatchContext
from app.session_storage import SessionStorage, default_session_storage
from app.detection import GameMapDetector, default_detector


# =====================================================================
# PHASE 4: SESSION LIFECYCLE STATE CONSTANTS
# =====================================================================

STATE_IDLE = "IDLE"
STATE_DETECTING = "DETECTING"
STATE_READY = "READY"
STATE_PLAYING = "PLAYING"
STATE_COMPLETED = "COMPLETED"

VALID_STATES = {STATE_IDLE, STATE_DETECTING, STATE_READY, STATE_PLAYING, STATE_COMPLETED}


# =====================================================================
# PHASE 4: SESSION LIFECYCLE MANAGER
# =====================================================================

class SessionLifecycleManager:
    """
    Coordinates the session lifecycle from detection to completion (Phase 4).
    
    States:
    IDLE -> DETECTING -> READY -> PLAYING -> COMPLETED
    
    Adheres strictly to requirements:
    - Creates Session on START SESSION with:
      session_id, game, game_mode, map, configuration, started_at, data_source.
    - Connects confirmed MatchContext to active Session.
    - Tracks duration live while PLAYING.
    - Stores ended_at and duration on END SESSION.
    - Allows post-session performance entry (score, kills, deaths, assists, result, player_notes).
    - Does NOT generate AI summaries yet.
    """

    def __init__(
        self,
        storage: Optional[SessionStorage] = None,
        detector: Optional[GameMapDetector] = None
    ):
        self.storage = storage or default_session_storage
        self.detector = detector or default_detector

        self.state: str = STATE_IDLE
        self.current_detection: Optional[DetectionResult] = None
        self.current_session: Optional[Session] = None
        self.started_at_dt: Optional[datetime] = None
        self.ended_at_dt: Optional[datetime] = None

    def start_gaming(
        self,
        source: str = "simulated",
        game_hint: Optional[str] = None,
        map_hint: Optional[str] = None,
        mode_hint: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence_override: Optional[float] = None
    ) -> DetectionResult:
        """
        Player initiates gaming session flow.
        Transitions: IDLE -> DETECTING -> READY
        """
        self.state = STATE_DETECTING

        detection = self.detector.detect(
            source=source,
            game_hint=game_hint,
            map_hint=map_hint,
            mode_hint=mode_hint,
            scenario=scenario,
            confidence_override=confidence_override
        )

        self.current_detection = detection
        self.state = STATE_READY
        return detection

    def confirm_and_start_session(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        configuration: Optional[Union[Dict[str, Any], str]] = None,
        session_id: Optional[Union[str, int]] = None,
        data_source: Optional[str] = None,
        started_at: Optional[Union[datetime, str]] = None,
        match_context: Optional[MatchContext] = None
    ) -> Session:
        """
        Player confirms detected/corrected telemetry and starts the session.
        Transitions: READY -> PLAYING
        Creates session in persistent storage and starts tracking duration.
        """
        resolved_game = game or (match_context.game if match_context else None) or (self.current_detection.game if self.current_detection else None)
        resolved_map = map_name or (match_context.map if match_context else None) or (self.current_detection.map if self.current_detection else None)
        resolved_mode = game_mode or (match_context.game_mode if match_context else None) or (self.current_detection.game_mode if self.current_detection else "Competitive")
        resolved_source = data_source or (match_context.detection_source if match_context else None) or (self.current_detection.detection_source if self.current_detection else "manual")

        if not resolved_game or not resolved_map:
            raise ValueError("Cannot start session without confirmed game and map.")

        # Set start timestamp
        if started_at is not None:
            if isinstance(started_at, datetime):
                start_dt = started_at
                start_str = start_dt.isoformat()
            else:
                start_str = str(started_at)
                try:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                except Exception:
                    start_dt = datetime.now()
        else:
            start_dt = datetime.now()
            start_str = start_dt.isoformat()

        self.started_at_dt = start_dt
        self.ended_at_dt = None

        sid = str(session_id) if session_id is not None else f"session-{int(start_dt.timestamp())}"

        session_payload: Dict[str, Any] = {
            "session_id": sid,
            "game": resolved_game,
            "game_mode": resolved_mode,
            "map": resolved_map,
            "started_at": start_str,
            "data_source": resolved_source
        }

        if match_context and match_context.match_id:
            session_payload["match_id"] = match_context.match_id
        if match_context and match_context.round_number is not None:
            session_payload["round_number"] = match_context.round_number
            session_payload["performance_metrics"] = {"round_number": match_context.round_number}

        if configuration is not None:
            session_payload["configuration"] = configuration

        # Persist session to storage layer
        created_session = self.storage.create_session(session_payload)
        self.current_session = created_session
        self.state = STATE_PLAYING

        return created_session

    def connect_match_context(self, match_context: MatchContext) -> Session:
        """
        Connects confirmed match context to active session.
        Updates persistent storage and local session reference.
        """
        if not self.current_session:
            raise ValueError("No active session found to connect match context to.")

        updated = self.detector.connect_confirmed_data_to_session(
            session_or_id=self.current_session,
            match_context=match_context,
            storage=self.storage
        )
        self.current_session = updated
        return updated

    def end_session(
        self,
        performance_data: Optional[Dict[str, Any]] = None,
        ended_at: Optional[Union[datetime, str]] = None,
        duration: Optional[Union[int, float, str]] = None
    ) -> Session:
        """
        Player ends the active session.
        Transitions: PLAYING -> COMPLETED
        Computes elapsed duration, sets ended_at, and applies post-session performance data.
        Does NOT generate AI summaries.
        """
        if not self.current_session:
            raise ValueError("No active session found to end.")

        # End timestamp calculation
        if ended_at is not None:
            if isinstance(ended_at, datetime):
                end_dt = ended_at
                end_str = end_dt.isoformat()
            else:
                end_str = str(ended_at)
                try:
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                except Exception:
                    end_dt = datetime.now()
        else:
            end_dt = datetime.now()
            end_str = end_dt.isoformat()

        self.ended_at_dt = end_dt

        # Duration calculation
        if duration is not None:
            final_duration = duration
        elif self.started_at_dt:
            total_seconds = max(1, int((end_dt - self.started_at_dt).total_seconds()))
            minutes = max(1, int(round(total_seconds / 60.0)))
            final_duration = minutes
        else:
            final_duration = 1

        update_payload: Dict[str, Any] = {
            "ended_at": end_str,
            "duration": final_duration
        }

        # Optional performance data entered upon session end
        if performance_data:
            allowed_fields = [
                "score", "kills", "deaths", "assists",
                "result", "player_notes", "performance_metrics",
                "tags", "configuration"
            ]
            for key in allowed_fields:
                if key in performance_data and performance_data[key] is not None:
                    update_payload[key] = performance_data[key]

        # Update in persistent storage
        updated_session = self.storage.update_session(
            session_id=self.current_session.session_id,
            update_data=update_payload
        )

        self.current_session = updated_session
        self.state = STATE_COMPLETED
        return updated_session

    def enter_performance_data(
        self,
        session_id: Optional[Union[str, int]] = None,
        score: Optional[str] = None,
        kills: Optional[int] = None,
        deaths: Optional[int] = None,
        assists: Optional[int] = None,
        result: Optional[str] = None,
        player_notes: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        tags: Optional[list] = None
    ) -> Session:
        """
        Allows entering or updating performance data after session completion.
        Preserves existing session fields and recomputes K/D automatically.
        Does NOT generate AI summaries.
        """
        sid = session_id or (self.current_session.session_id if self.current_session else None)
        if not sid:
            raise ValueError("session_id must be provided to enter performance data.")

        update_payload: Dict[str, Any] = {}
        if score is not None:
            update_payload["score"] = score
        if kills is not None:
            update_payload["kills"] = kills
        if deaths is not None:
            update_payload["deaths"] = deaths
        if assists is not None:
            update_payload["assists"] = assists
        if result is not None:
            update_payload["result"] = result
        if player_notes is not None:
            update_payload["player_notes"] = player_notes
        if performance_metrics is not None:
            update_payload["performance_metrics"] = performance_metrics
        if tags is not None:
            update_payload["tags"] = tags

        updated = self.storage.update_session(session_id=sid, update_data=update_payload)
        if self.current_session and str(self.current_session.session_id) == str(sid):
            self.current_session = updated
        return updated

    def reset_to_idle(self) -> None:
        """Resets the lifecycle state back to IDLE for the next gaming session."""
        self.state = STATE_IDLE
        self.current_detection = None
        self.current_session = None
        self.started_at_dt = None
        self.ended_at_dt = None

    def get_status(self) -> Dict[str, Any]:
        """Returns the current real-time status of the session lifecycle."""
        elapsed_seconds = 0
        if self.state == STATE_PLAYING and self.started_at_dt:
            elapsed_seconds = int((datetime.now() - self.started_at_dt).total_seconds())

        sid = self.current_session.session_id if self.current_session else None
        game = (
            self.current_session.game if self.current_session else (
                self.current_detection.game if self.current_detection else None
            )
        )
        map_name = (
            self.current_session.map if self.current_session else (
                self.current_detection.map if self.current_detection else None
            )
        )

        return {
            "state": self.state,
            "session_id": sid,
            "game": game,
            "map": map_name,
            "elapsed_seconds": elapsed_seconds,
            "started_at": self.started_at_dt.isoformat() if self.started_at_dt else None,
            "ended_at": self.ended_at_dt.isoformat() if self.ended_at_dt else None,
            "current_session": self.current_session.model_dump() if self.current_session else None,
            "current_detection": self.current_detection.model_dump() if self.current_detection else None
        }


# Default singleton manager
default_lifecycle_manager = SessionLifecycleManager()
