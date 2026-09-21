"""
Phase 9: Lightweight Real-Time Performance Analysis Layer.

Processes available game events during an active session:
- kill
- death
- assist
- objective
- location change
- round result
- match result
- inventory/configuration change

Calculates live metrics:
- current K/D
- kills
- deaths
- survival time
- objective progress
- current score

Strict rules:
1. Do not implement advanced computer vision (uses simulated events or available telemetry).
2. Do not generate unsupported recommendations.
3. Do not interfere with game controls: purely observational and analytical.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re

from app.models import GameEvent, CurrentPerformance, GAME_EVENT_TYPES
from app.session_lifecycle import SessionLifecycleManager, default_lifecycle_manager


class RealtimePerformanceAnalyzer:
    """
    Phase 9: Lightweight Real-Time Performance Analyzer.
    Processes live or simulated game events during an active match to track
    live K/D, survival time, kills, deaths, assists, objective progress, and score.
    Never interferes with game controls.
    Never generates unsupported recommendations.
    """

    def __init__(self, lifecycle_manager: Optional[SessionLifecycleManager] = None):
        self.lifecycle_manager = lifecycle_manager or default_lifecycle_manager
        self.started_at: Optional[datetime] = None
        self.state = CurrentPerformance()

    def start_session(
        self,
        session_id: Optional[str] = None,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        initial_config: Optional[str] = None
    ) -> CurrentPerformance:
        """Initializes a new live performance tracking session."""
        self.started_at = datetime.now()
        self.state = CurrentPerformance(
            session_id=session_id,
            game=game,
            map=map_name,
            kd_ratio=0.0,
            kills=0,
            deaths=0,
            assists=0,
            survival_time="0 min",
            survival_time_seconds=0.0,
            objective_progress=None,
            current_score=None,
            current_location=None,
            current_configuration=initial_config,
            round_number=1,
            recent_events=[]
        )
        return self.state

    def process_event(self, event_data: Union[GameEvent, Dict[str, Any]]) -> CurrentPerformance:
        """
        Processes an incoming live game event (simulated or real telemetry).
        Updates measurable metrics without generating unsupported recommendations.
        """
        if isinstance(event_data, dict):
            event_type_raw = str(event_data.get("event_type", "")).strip().lower()
            details = event_data.get("details", {})
            event_id = event_data.get("event_id")
            timestamp = event_data.get("timestamp") or datetime.now().isoformat()
            event = GameEvent(
                event_id=event_id or f"evt-{len(self.state.recent_events) + 1}",
                event_type=event_type_raw,
                timestamp=timestamp,
                details=details
            )
        else:
            event = event_data
            event_type_raw = event.event_type.strip().lower()
            details = event.details

        # Normalize event type aliases
        normalized_type = event_type_raw.replace(" ", "_").replace("-", "_")

        # 1. KILL
        if normalized_type == "kill":
            count = int(details.get("count", 1))
            self.state.kills += count
            if details.get("score"):
                self.state.current_score = details.get("score")

        # 2. DEATH
        elif normalized_type == "death":
            count = int(details.get("count", 1))
            self.state.deaths += count

        # 3. ASSIST
        elif normalized_type == "assist":
            count = int(details.get("count", 1))
            self.state.assists += count

        # 4. OBJECTIVE
        elif normalized_type == "objective":
            action = details.get("action") or details.get("objective_type") or "objective"
            progress = details.get("progress")
            points = details.get("points") or details.get("score")
            zone = details.get("zone") or details.get("site")

            if progress:
                self.state.objective_progress = str(progress)
            elif zone:
                self.state.objective_progress = f"{action.title()} {zone}"
            else:
                self.state.objective_progress = str(action).title()

            if points is not None:
                if isinstance(self.state.current_score, (int, float)) and isinstance(points, (int, float)):
                    self.state.current_score += points
                else:
                    self.state.current_score = points

        # 5. LOCATION CHANGE
        elif normalized_type in ("location_change", "location"):
            new_loc = details.get("location") or details.get("zone") or details.get("area")
            if new_loc:
                self.state.current_location = str(new_loc)

        # 6. ROUND RESULT
        elif normalized_type in ("round_result", "round"):
            round_num = details.get("round_number") or details.get("round")
            if round_num is not None:
                try:
                    self.state.round_number = int(round_num)
                except ValueError:
                    pass
            elif self.state.round_number:
                self.state.round_number += 1
            else:
                self.state.round_number = 1

            score = details.get("score") or details.get("round_score")
            if score is not None:
                self.state.current_score = score

        # 7. MATCH RESULT
        elif normalized_type in ("match_result", "match_finished", "result"):
            res = details.get("result") or details.get("outcome")
            if res:
                if isinstance(self.state.current_score, str):
                    self.state.current_score += f" ({res})"
                else:
                    self.state.current_score = str(res)

        # 8. INVENTORY / CONFIGURATION CHANGE
        elif normalized_type in (
            "configuration_change", "inventory_change",
            "inventory", "configuration", "weapon_change"
        ):
            new_cfg = (
                details.get("configuration")
                or details.get("weapon")
                or details.get("loadout")
                or details.get("item")
            )
            if new_cfg:
                self.state.current_configuration = str(new_cfg)

        # Update K/D safely
        if self.state.deaths == 0:
            self.state.kd_ratio = float(self.state.kills)
        else:
            self.state.kd_ratio = round(float(self.state.kills) / float(self.state.deaths), 2)

        # Update Survival Time
        if details.get("survival_time"):
            raw_surv = str(details.get("survival_time")).strip()
            self.state.survival_time = raw_surv if raw_surv.endswith("min") else f"{raw_surv} min"
        elif details.get("survival_time_seconds") is not None:
            secs = float(details.get("survival_time_seconds"))
            self.state.survival_time_seconds = secs
            self.state.survival_time = f"{int(secs // 60)} min"
        elif self.started_at:
            elapsed_secs = (datetime.now() - self.started_at).total_seconds()
            self.state.survival_time_seconds = elapsed_secs
            self.state.survival_time = f"{int(elapsed_secs // 60)} min"

        # Record in audit trail
        self.state.recent_events.append(event)

        return self.state

    def simulate_event(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> CurrentPerformance:
        """Simulates an in-game telemetry event for real-time testing."""
        if session_id and not self.state.session_id:
            self.state.session_id = session_id

        payload = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        return self.process_event(payload)

    def get_current_performance(self) -> CurrentPerformance:
        """
        Retrieves the current live performance state.
        Updates elapsed survival time if tracking an active session.
        """
        if self.started_at and not self.state.survival_time:
            elapsed_secs = (datetime.now() - self.started_at).total_seconds()
            self.state.survival_time_seconds = elapsed_secs
            self.state.survival_time = f"{int(elapsed_secs // 60)} min"
        return self.state

    def reset(self) -> None:
        """Resets the live performance analyzer state."""
        self.started_at = None
        self.state = CurrentPerformance()


# Global default real-time performance analyzer
default_realtime_analyzer = RealtimePerformanceAnalyzer()
