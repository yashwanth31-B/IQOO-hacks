"""
Phase 6: Generic Gaming Performance Engine.

Calculates measurable performance metrics from stored session data.
Strict rules:
1. Do not calculate or estimate metrics when required data is missing.
   Returns "Not enough data." when a metric is unavailable.
2. Safe calculations (e.g., K/D handles zero deaths without division errors).
3. Normalized Performance Report generation.
4. Game-specific metrics extensible.
5. Do not create recommendations yet.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re

from app.models import Session, PerformanceReport
from app.session_storage import SessionStorage, default_session_storage as default_storage


def parse_duration_minutes(
    duration_val: Any,
    started_at: Optional[Union[datetime, str]] = None,
    ended_at: Optional[Union[datetime, str]] = None,
) -> Optional[float]:
    """
    Safely parses session duration in minutes.
    Does not estimate if data is completely absent.
    """
    if duration_val is not None:
        if isinstance(duration_val, (int, float)):
            if duration_val >= 0:
                return float(duration_val)
            return None
        if isinstance(duration_val, str):
            val_clean = duration_val.strip().lower()
            # Try plain number
            try:
                mins = float(val_clean)
                if mins >= 0:
                    return mins
            except ValueError:
                pass

            # Match "72 min", "72 mins", "72m", "72 minutes"
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|m\b)", val_clean)
            if match:
                return float(match.group(1))

            # Match HH:MM:SS or MM:SS
            time_parts = val_clean.split(":")
            if len(time_parts) == 3:
                try:
                    h, m, s = int(time_parts[0]), int(time_parts[1]), float(time_parts[2])
                    return round(h * 60.0 + m + s / 60.0, 2)
                except ValueError:
                    pass
            elif len(time_parts) == 2:
                try:
                    m, s = int(time_parts[0]), float(time_parts[1])
                    return round(m + s / 60.0, 2)
                except ValueError:
                    pass

    # Fallback to started_at / ended_at timestamps if available
    if started_at and ended_at:
        try:
            start_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00")) if isinstance(started_at, str) else started_at
            end_dt = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00")) if isinstance(ended_at, str) else ended_at
            diff_secs = (end_dt - start_dt).total_seconds()
            if diff_secs >= 0:
                return round(diff_secs / 60.0, 2)
        except Exception:
            pass

    return None


def format_duration_display(duration_mins: Optional[float], raw_val: Any = None) -> Optional[str]:
    """
    Formats duration string e.g. '72 min' matching Phase 6 specification.
    """
    if raw_val is not None and isinstance(raw_val, str) and "min" in raw_val.lower():
        # Clean up spacing e.g. '72 min'
        val = raw_val.strip()
        match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:min|mins|minutes)$", val, re.IGNORECASE)
        if match:
            num = float(match.group(1))
            display_num = int(num) if num.is_integer() else num
            return f"{display_num} min"
        return raw_val

    if duration_mins is not None:
        display_num = int(duration_mins) if duration_mins.is_integer() else round(duration_mins, 1)
        return f"{display_num} min"

    return None


class GamingPerformanceEngine:
    """
    Phase 6: Generic Gaming Performance Engine.
    Calculates measurable performance metrics from stored session data.
    Never invents or estimates missing metrics.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_storage

    def calculate_session_performance(
        self, session_data: Union[Session, Dict[str, Any]]
    ) -> PerformanceReport:
        """
        Calculates measurable performance metrics for a single session.
        If any metric's input is missing, it is NOT estimated and left as None.
        """
        if isinstance(session_data, dict):
            # Convert to Session or extract fields safely
            try:
                session = Session(**session_data)
            except Exception:
                session = None
            raw_dict = session_data
        else:
            session = session_data
            raw_dict = session.model_dump() if hasattr(session, "model_dump") else session.__dict__

        session_id = raw_dict.get("session_id") or raw_dict.get("id")
        game = raw_dict.get("game")
        game_map = raw_dict.get("map") or raw_dict.get("map_or_level")
        raw_result = raw_dict.get("result") or raw_dict.get("outcome")

        # Telemetry containers
        perf_metrics = raw_dict.get("performance_metrics") or raw_dict.get("stats") or {}
        if not isinstance(perf_metrics, dict):
            perf_metrics = {}

        available_metrics: List[str] = []
        missing_metrics: List[str] = []

        # 1. Kills, Deaths, Assists
        kills = raw_dict.get("kills")
        if kills is not None and isinstance(kills, (int, float)) and kills >= 0:
            kills = int(kills)
            available_metrics.append("kills")
        else:
            kills = None
            missing_metrics.append("kills")

        deaths = raw_dict.get("deaths")
        if deaths is not None and isinstance(deaths, (int, float)) and deaths >= 0:
            deaths = int(deaths)
            available_metrics.append("deaths")
        else:
            deaths = None
            missing_metrics.append("deaths")

        assists = raw_dict.get("assists")
        if assists is not None and isinstance(assists, (int, float)) and assists >= 0:
            assists = int(assists)
            available_metrics.append("assists")
        else:
            assists = None
            missing_metrics.append("assists")

        # 2. K/D Ratio
        kd_ratio: Optional[float] = None
        if kills is not None and deaths is not None:
            if deaths == 0:
                kd_ratio = float(kills)
            else:
                kd_ratio = round(kills / deaths, 2)
            available_metrics.append("kd_ratio")
        else:
            missing_metrics.append("kd_ratio")

        # 3. Duration & Survival Duration
        raw_dur = raw_dict.get("duration") or raw_dict.get("duration_mins")
        started_at = raw_dict.get("started_at") or raw_dict.get("date") or raw_dict.get("timestamp")
        ended_at = raw_dict.get("ended_at")

        duration_mins = parse_duration_minutes(raw_dur, started_at, ended_at)
        duration_display = format_duration_display(duration_mins, raw_dur)

        if duration_mins is not None:
            available_metrics.append("duration")
        else:
            missing_metrics.append("duration")

        # Survival duration (from performance_metrics or duration if battle royale)
        survival_duration: Optional[Union[float, str]] = None
        raw_survival = perf_metrics.get("survival_duration") or perf_metrics.get("survival_time")
        if raw_survival is not None:
            survival_duration = raw_survival
            available_metrics.append("survival_duration")
        elif duration_display is not None and game and any(br in game.lower() for br in ["bgmi", "pubg", "free fire"]):
            # For Battle Royale games where session duration is survival duration
            survival_duration = duration_display
            available_metrics.append("survival_duration")
        else:
            missing_metrics.append("survival_duration")

        # 4. Result & Win Rate
        result = str(raw_result).strip() if raw_result else None
        win_rate: Optional[float] = None
        if result:
            available_metrics.append("result")
            res_lower = result.lower()
            if any(w in res_lower for w in ["win", "victory", "1st", "won", "champion"]):
                win_rate = 100.0
                available_metrics.append("win_rate")
            elif any(l in res_lower for l in ["loss", "defeat", "lost", "2nd", "3rd", "eliminated"]):
                win_rate = 0.0
                available_metrics.append("win_rate")
            elif any(d in res_lower for d in ["draw", "tie"]):
                win_rate = 0.0
                available_metrics.append("win_rate")
            else:
                missing_metrics.append("win_rate")
        else:
            missing_metrics.append("result")
            missing_metrics.append("win_rate")

        # 5. Kills Per Minute (KPM) & Deaths Per Minute (DPM)
        kills_per_minute: Optional[float] = None
        if kills is not None and duration_mins is not None and duration_mins > 0:
            kills_per_minute = round(kills / duration_mins, 2)
            available_metrics.append("kills_per_minute")
        else:
            missing_metrics.append("kills_per_minute")

        deaths_per_minute: Optional[float] = None
        if deaths is not None and duration_mins is not None and duration_mins > 0:
            deaths_per_minute = round(deaths / duration_mins, 2)
            available_metrics.append("deaths_per_minute")
        else:
            missing_metrics.append("deaths_per_minute")

        # 6. Score Efficiency
        score_efficiency: Optional[float] = None
        raw_score = raw_dict.get("score") or perf_metrics.get("score")
        if raw_score is not None and duration_mins is not None and duration_mins > 0:
            # Check if numeric score
            try:
                numeric_score = float(raw_score)
                score_efficiency = round(numeric_score / duration_mins, 2)
                available_metrics.append("score_efficiency")
            except (ValueError, TypeError):
                # Try round format e.g. "13-11" or "18/10"
                if isinstance(raw_score, str) and ("-" in raw_score or "/" in raw_score):
                    sep = "-" if "-" in raw_score else "/"
                    parts = raw_score.split(sep)
                    try:
                        pts = float(parts[0].strip())
                        score_efficiency = round(pts / duration_mins, 2)
                        available_metrics.append("score_efficiency")
                    except ValueError:
                        missing_metrics.append("score_efficiency")
                else:
                    missing_metrics.append("score_efficiency")
        else:
            missing_metrics.append("score_efficiency")

        # 7. Accuracy (when available - DO NOT estimate)
        accuracy: Optional[Union[float, str]] = None
        raw_accuracy = (
            perf_metrics.get("accuracy")
            or perf_metrics.get("shot_accuracy")
            or perf_metrics.get("hit_accuracy")
            or perf_metrics.get("weapon_accuracy")
        )
        if raw_accuracy is not None:
            accuracy = raw_accuracy
            available_metrics.append("accuracy")
        else:
            missing_metrics.append("accuracy")

        # 8. Damage (when available - DO NOT estimate)
        damage: Optional[Union[float, int]] = None
        raw_damage = (
            perf_metrics.get("damage")
            or perf_metrics.get("damage_dealt")
            or perf_metrics.get("total_damage")
        )
        if raw_damage is not None:
            try:
                damage = float(raw_damage) if "." in str(raw_damage) else int(raw_damage)
                available_metrics.append("damage")
            except (ValueError, TypeError):
                damage = raw_damage
                available_metrics.append("damage")
        else:
            missing_metrics.append("damage")

        # 9. Objective Performance (when available - DO NOT estimate)
        objective_performance: Optional[Union[Dict[str, Any], float, str]] = None
        raw_obj = (
            perf_metrics.get("objective_performance")
            or perf_metrics.get("objectives_captured")
            or perf_metrics.get("bomb_plants")
            or perf_metrics.get("defuses")
            or perf_metrics.get("captures")
        )
        if raw_obj is not None:
            objective_performance = raw_obj
            available_metrics.append("objective_performance")
        else:
            missing_metrics.append("objective_performance")

        # 10. Extensible game-specific metrics
        # Collect anything else in performance_metrics that was not captured above
        standard_keys = {
            "accuracy", "shot_accuracy", "hit_accuracy", "weapon_accuracy",
            "damage", "damage_dealt", "total_damage",
            "objective_performance", "objectives_captured", "bomb_plants", "defuses", "captures",
            "survival_duration", "survival_time", "score"
        }
        game_specific_metrics = {
            k: v for k, v in perf_metrics.items() if k not in standard_keys
        }

        return PerformanceReport(
            session_id=session_id,
            game=game,
            map=game_map,
            kd_ratio=kd_ratio,
            kills=kills,
            deaths=deaths,
            assists=assists,
            win_rate=win_rate,
            duration_mins=duration_mins,
            duration_display=duration_display,
            survival_duration=survival_duration,
            result=result,
            kills_per_minute=kills_per_minute,
            deaths_per_minute=deaths_per_minute,
            score_efficiency=score_efficiency,
            accuracy=accuracy,
            damage=damage,
            objective_performance=objective_performance,
            game_specific_metrics=game_specific_metrics,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
        )

    def calculate_session_by_id(self, session_id: Union[str, int]) -> PerformanceReport:
        """
        Retrieves a stored session from storage and calculates its PerformanceReport.
        """
        session = None
        if hasattr(self.storage, "get_session_by_id"):
            session = self.storage.get_session_by_id(session_id)
        elif hasattr(self.storage, "get_session"):
            session = self.storage.get_session(session_id)

        if not session:
            try:
                from app.database import get_session_by_id
                s_dict = get_session_by_id(int(session_id))
                if s_dict:
                    return self.calculate_session_performance(s_dict)
            except Exception:
                pass
            raise ValueError(f"Session '{session_id}' not found in storage.")
        return self.calculate_session_performance(session)

    def calculate_aggregate_performance(
        self, sessions: List[Union[Session, Dict[str, Any]]], game: Optional[str] = None
    ) -> PerformanceReport:
        """
        Calculates aggregate measurable performance across multiple stored sessions.
        Strictly computes from available factual data.
        """
        filtered_sessions: List[Union[Session, Dict[str, Any]]] = []
        for s in sessions:
            g = s.game if isinstance(s, Session) else s.get("game")
            if game is None or (g and g.lower() == game.lower()):
                filtered_sessions.append(s)

        if not filtered_sessions:
            return PerformanceReport(
                game=game,
                missing_metrics=[
                    "kd_ratio", "kills", "deaths", "assists", "win_rate",
                    "duration", "accuracy", "damage", "objective_performance"
                ]
            )

        total_kills = 0
        has_kills = False
        total_deaths = 0
        has_deaths = False
        total_assists = 0
        has_assists = False

        total_duration_mins = 0.0
        has_duration = False

        total_wins = 0
        sessions_with_result = 0

        accuracies: List[float] = []
        damages: List[float] = []

        available_metrics: List[str] = []
        missing_metrics: List[str] = []

        for s in filtered_sessions:
            report = self.calculate_session_performance(s)

            if report.kills is not None:
                total_kills += report.kills
                has_kills = True
            if report.deaths is not None:
                total_deaths += report.deaths
                has_deaths = True
            if report.assists is not None:
                total_assists += report.assists
                has_assists = True
            if report.duration_mins is not None:
                total_duration_mins += report.duration_mins
                has_duration = True
            if report.win_rate is not None:
                sessions_with_result += 1
                if report.win_rate == 100.0:
                    total_wins += 1
            if report.accuracy is not None:
                try:
                    acc_val = float(str(report.accuracy).replace("%", "").strip())
                    accuracies.append(acc_val)
                except ValueError:
                    pass
            if report.damage is not None:
                try:
                    dmg_val = float(report.damage)
                    damages.append(dmg_val)
                except ValueError:
                    pass

        # Aggregate K/D
        agg_kd: Optional[float] = None
        if has_kills and has_deaths:
            agg_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else float(total_kills)
            available_metrics.append("kd_ratio")
        else:
            missing_metrics.append("kd_ratio")

        # Aggregate Win Rate
        agg_win_rate: Optional[float] = None
        if sessions_with_result > 0:
            agg_win_rate = round((total_wins / sessions_with_result) * 100.0, 1)
            available_metrics.append("win_rate")
        else:
            missing_metrics.append("win_rate")

        # KPM & DPM
        agg_kpm: Optional[float] = None
        if has_kills and has_duration and total_duration_mins > 0:
            agg_kpm = round(total_kills / total_duration_mins, 2)
            available_metrics.append("kills_per_minute")
        else:
            missing_metrics.append("kills_per_minute")

        agg_dpm: Optional[float] = None
        if has_deaths and has_duration and total_duration_mins > 0:
            agg_dpm = round(total_deaths / total_duration_mins, 2)
            available_metrics.append("deaths_per_minute")
        else:
            missing_metrics.append("deaths_per_minute")

        # Accuracy & Damage
        agg_accuracy: Optional[Union[float, str]] = None
        if accuracies:
            agg_accuracy = round(sum(accuracies) / len(accuracies), 2)
            available_metrics.append("accuracy")
        else:
            missing_metrics.append("accuracy")

        agg_damage: Optional[Union[float, int]] = None
        if damages:
            agg_damage = round(sum(damages) / len(damages), 1)
            available_metrics.append("damage")
        else:
            missing_metrics.append("damage")

        duration_display = format_duration_display(total_duration_mins) if has_duration else None

        return PerformanceReport(
            game=game,
            kd_ratio=agg_kd,
            kills=total_kills if has_kills else None,
            deaths=total_deaths if has_deaths else None,
            assists=total_assists if has_assists else None,
            win_rate=agg_win_rate,
            duration_mins=total_duration_mins if has_duration else None,
            duration_display=duration_display,
            kills_per_minute=agg_kpm,
            deaths_per_minute=agg_dpm,
            accuracy=agg_accuracy,
            damage=agg_damage,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
        )


# Global default instance
default_performance_engine = GamingPerformanceEngine()
