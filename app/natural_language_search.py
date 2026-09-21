import re
import json
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

from app.models import (
    Session,
    StructuredQuery,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse
)
from app.session_storage import SessionStorage, default_session_storage


NOT_ENOUGH_DATA = "Not enough data to determine this."

KNOWN_MAPS = [
    "ascent", "haven", "bind", "split", "lotus", "sunset", "breeze", "fracture", "icebox", "abyss",
    "world's edge", "storm point", "kings canyon", "olympus", "broken moon",
    "elphael", "haligtree", "limgrave", "caelid", "leyndell"
]

KNOWN_GAMES = [
    "valorant", "apex legends", "apex", "elden ring", "overwatch", "csgo", "counter-strike"
]

KNOWN_WEAPONS = [
    "phantom", "vandal", "operator", "sheriff", "spectre", "odin",
    "r-99", "wingman", "peacekeeper", "flatline", "nemesis",
    "rivers of blood", "moonveil"
]

def extract_session_ids(text: str) -> List[str]:
    """Extracts explicit session IDs like 'Session #18', 'Session 14', 'Session #abc-123'."""
    matches = []
    for m in re.finditer(r'session\s*(?:#([a-zA-Z0-9_\-]+)|\b(\d+)\b)', text, re.IGNORECASE):
        sid = m.group(1) or m.group(2)
        if sid and sid.lower() not in ("s", "compare", "info", "data", "history", "telemetry"):
            matches.append(sid)
    return matches


# =====================================================================
# PHASE 7: NATURAL LANGUAGE SEARCH ENGINE
# =====================================================================

class NaturalLanguageSearchEngine:
    """
    Phase 7 Natural Language Search Engine for Gaming Second Brain.
    
    Architecture:
    User Question -> Intent Detection -> Structured Query -> Session Retrieval -> Return Relevant Evidence
    
    Adheres strictly to Phase 7 requirements:
    - Supported intents:
        * best_session
        * worst_session
        * recent_performance
        * map_performance
        * configuration_performance
        * improvement
        * session_duration
        * performance_comparison
    - StructuredQuery containing: intent, filters, sort, limit, required_metrics, comparison_needed
    - Strict hallucination protection: Never generate unsupported answers.
      If data is unavailable or insufficient: "Not enough data to determine this."
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage

    # -----------------------------------------------------------------
    # STEP 1 & 2: INTENT DETECTION -> STRUCTURED QUERY
    # -----------------------------------------------------------------
    def parse_query_to_structured(
        self,
        query: str,
        pre_filters: Optional[Dict[str, Any]] = None
    ) -> StructuredQuery:
        """
        Parses a natural language question into a formal StructuredQuery.
        Extracts intent, filters, sort order, metrics, and comparison requirement.
        """
        q_lower = query.lower().strip()
        filters = dict(pre_filters) if pre_filters else {}

        # 1. Extract Game Filter if mentioned
        for g in KNOWN_GAMES:
            if g in q_lower:
                canonical_game = "Valorant" if g == "valorant" else ("Apex Legends" if "apex" in g else ("Elden Ring" if "elden" in g else g.title()))
                filters["game"] = canonical_game
                break

        # 2. Extract Map Filter if mentioned
        target_map = None
        for m in KNOWN_MAPS:
            if re.search(r'\b' + re.escape(m) + r'\b', q_lower):
                target_map = m.title()
                filters["map"] = target_map
                break

        # 3. Extract Weapon / Configuration Filter if mentioned
        target_weapon = None
        for w in KNOWN_WEAPONS:
            if re.search(r'\b' + re.escape(w) + r'\b', q_lower):
                target_weapon = w.title()
                filters["configuration"] = target_weapon
                break

        # 4. Check for Specific Session IDs in query (e.g. "Session #18", "Session 14")
        session_id_matches = extract_session_ids(q_lower)

        # -------------------------------------------------------------
        # Intent Classification (Precedence-based heuristic NLP)
        # -------------------------------------------------------------
        # Intent: map_performance
        if any(w in q_lower for w in ["map", "maps"]) or (target_map and any(p in q_lower for p in ["perform", "how do i", "play on", "win rate"])):
            return StructuredQuery(
                intent="map_performance",
                filters=filters,
                sort="kd_ratio DESC",
                limit=10,
                required_metrics=["map", "kd_ratio", "result"],
                comparison_needed=True,
                target_entity=target_map
            )

        # Intent: configuration_performance
        if any(w in q_lower for w in ["configuration", "loadout", "weapon", "sensitivity", "gear", "build", "setup"]) or (target_weapon and any(p in q_lower for p in ["perform", "play with", "do with", "best with", "k/d"])):
            return StructuredQuery(
                intent="configuration_performance",
                filters=filters,
                sort="kd_ratio DESC",
                limit=10,
                required_metrics=["configuration", "kd_ratio", "result"],
                comparison_needed=True,
                target_entity=target_weapon
            )

        # Intent: session_duration
        if any(w in q_lower for w in ["duration", "how long", "session length", "minutes", "hours", "longer", "shorter"]):
            return StructuredQuery(
                intent="session_duration",
                filters=filters,
                sort="duration DESC",
                limit=10,
                required_metrics=["duration", "kd_ratio"],
                comparison_needed=True
            )

        # Intent: improvement
        if any(w in q_lower for w in ["improving", "improvement", "getting better", "getting worse", "progress", "progressing", "aim better"]):
            return StructuredQuery(
                intent="improvement",
                filters=filters,
                sort="started_at ASC",
                limit=20,
                required_metrics=["kd_ratio", "started_at"],
                comparison_needed=True
            )

        # Intent: performance_comparison
        if any(w in q_lower for w in ["compare", "comparison", "different", "versus", "vs"]) or len(session_id_matches) >= 2:
            return StructuredQuery(
                intent="performance_comparison",
                filters=filters,
                sort="started_at DESC",
                limit=len(session_id_matches) if len(session_id_matches) >= 2 else 2,
                required_metrics=["kd_ratio", "kills", "deaths", "result"],
                comparison_needed=True,
                target_entity=", ".join(session_id_matches) if session_id_matches else None
            )

        # Intent: worst_session
        if any(w in q_lower for w in ["worst", "lowest", "poorest", "bad game", "terrible", "perform worst"]):
            return StructuredQuery(
                intent="worst_session",
                filters=filters,
                sort="kd_ratio ASC",
                limit=1,
                required_metrics=["kd_ratio", "kills", "deaths", "result"],
                comparison_needed=False
            )

        # Intent: recent_performance
        if any(w in q_lower for w in ["recent", "recently", "lately", "last few", "past few", "latest"]):
            return StructuredQuery(
                intent="recent_performance",
                filters=filters,
                sort="started_at DESC",
                limit=3,
                required_metrics=["kd_ratio", "result", "duration"],
                comparison_needed=False
            )

        # Intent: best_session (Default for best performance questions)
        if any(w in q_lower for w in ["best", "highest", "top", "peak", "strongest", "perform best", "when did i perform best"]):
            return StructuredQuery(
                intent="best_session",
                filters=filters,
                sort="kd_ratio DESC",
                limit=1,
                required_metrics=["kd_ratio", "kills", "deaths", "result"],
                comparison_needed=False
            )

        # Fallback default: recent_performance
        return StructuredQuery(
            intent="recent_performance",
            filters=filters,
            sort="started_at DESC",
            limit=5,
            required_metrics=["kd_ratio", "result"],
            comparison_needed=False
        )

    # -----------------------------------------------------------------
    # STEP 3: SESSION RETRIEVAL
    # -----------------------------------------------------------------
    def retrieve_sessions_for_query(self, query: StructuredQuery) -> List[Session]:
        """
        Fetches stored sessions matching query filters and sorting criteria.
        """
        all_sessions = self.storage.get_recent_sessions(limit=100)
        if not all_sessions:
            return []

        filtered = []
        for s in all_sessions:
            match = True
            # Game filter
            if "game" in query.filters:
                req_game = str(query.filters["game"]).lower()
                if not s.game or req_game not in s.game.lower():
                    match = False

            # Map filter
            if match and "map" in query.filters:
                req_map = str(query.filters["map"]).lower()
                if not s.map or req_map not in s.map.lower():
                    match = False

            # Configuration filter
            if match and "configuration" in query.filters:
                req_cfg = str(query.filters["configuration"]).lower()
                cfg_str = str(s.configuration or "").lower()
                if req_cfg not in cfg_str:
                    match = False

            if match:
                filtered.append(s)

        if not filtered:
            return []

        # Sorting logic
        sort_field = query.sort or "started_at DESC"
        field_name = sort_field.split()[0].lower()
        is_desc = "desc" in sort_field.lower()

        def sort_key(s: Session):
            if field_name == "kd_ratio":
                return s.kd_ratio if s.kd_ratio is not None else -1.0
            elif field_name == "duration":
                if isinstance(s.duration, (int, float)):
                    return s.duration
                if isinstance(s.duration, str):
                    digits = "".join([c for c in s.duration if c.isdigit()])
                    return int(digits) if digits else 0
                return 0
            elif field_name in ("started_at", "date", "id"):
                return str(s.started_at or s.id or "")
            return 0

        # Sort filtered sessions
        filtered.sort(key=sort_key, reverse=is_desc)

        return filtered[:query.limit]

    # -----------------------------------------------------------------
    # STEP 4: EVIDENCE SYNTHESIS & ANSWER FORMULATION
    # -----------------------------------------------------------------
    def search(
        self,
        query_text: str,
        pre_filters: Optional[Dict[str, Any]] = None
    ) -> NaturalLanguageSearchResponse:
        """
        Executes end-to-end Natural Language Search.
        Never generates unsupported claims. If data is unavailable:
        returns 'Not enough data to determine this.'
        """
        structured = self.parse_query_to_structured(query_text, pre_filters)
        intent = structured.intent

        # Dispatch based on detected intent
        if intent == "best_session":
            return self._answer_best_session(query_text, structured)
        elif intent == "worst_session":
            return self._answer_worst_session(query_text, structured)
        elif intent == "recent_performance":
            return self._answer_recent_performance(query_text, structured)
        elif intent == "map_performance":
            return self._answer_map_performance(query_text, structured)
        elif intent == "configuration_performance":
            return self._answer_configuration_performance(query_text, structured)
        elif intent == "improvement":
            return self._answer_improvement(query_text, structured)
        elif intent == "session_duration":
            return self._answer_session_duration(query_text, structured)
        elif intent == "performance_comparison":
            return self._answer_performance_comparison(query_text, structured)
        else:
            return self._answer_recent_performance(query_text, structured)

    # -----------------------------------------------------------------
    # INTENT HANDLERS
    # -----------------------------------------------------------------

    # 1. Best Session
    def _answer_best_session(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        sessions = self.retrieve_sessions_for_query(structured)
        valid_sessions = [s for s in sessions if s.kd_ratio is not None]

        if not valid_sessions:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        best = valid_sessions[0]
        sid = str(best.session_id or best.id)

        details = []
        if best.kills is not None and best.deaths is not None:
            details.append(f"{best.kills} kills, {best.deaths} deaths")
        if best.score:
            details.append(f"score {best.score}")
        det_str = f" ({', '.join(details)})" if details else ""

        map_str = f" on {best.map}" if best.map else ""
        cfg_str = ""
        if best.configuration:
            if isinstance(best.configuration, dict):
                w = best.configuration.get("primary_weapon") or best.configuration.get("weapon")
                cfg_str = f" using {w} configuration" if w else ""
            else:
                cfg_str = f" using {best.configuration}"

        res_str = f" with a {best.result}" if best.result else ""

        answer = f"Your best recorded session was Session #{sid}. You achieved a {best.kd_ratio:.1f} K/D{det_str}{map_str}{cfg_str}{res_str}."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=[sid],
            evidence_sessions=[best.model_dump()],
            metrics_used={"kd_ratio": best.kd_ratio, "kills": best.kills, "deaths": best.deaths},
            status="answered"
        )

    # 2. Worst Session
    def _answer_worst_session(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        sessions = self.retrieve_sessions_for_query(structured)
        valid_sessions = [s for s in sessions if s.kd_ratio is not None]

        if not valid_sessions:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        worst = valid_sessions[0]
        sid = str(worst.session_id or worst.id)

        details = []
        if worst.kills is not None and worst.deaths is not None:
            details.append(f"{worst.kills} kills, {worst.deaths} deaths")
        det_str = f" ({', '.join(details)})" if details else ""

        map_str = f" on {worst.map}" if worst.map else ""
        res_str = f" resulting in a {worst.result}" if worst.result else ""

        answer = f"Your lowest recorded performance was Session #{sid}. You recorded a {worst.kd_ratio:.1f} K/D{det_str}{map_str}{res_str}."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=[sid],
            evidence_sessions=[worst.model_dump()],
            metrics_used={"kd_ratio": worst.kd_ratio, "kills": worst.kills, "deaths": worst.deaths},
            status="answered"
        )

    # 3. Recent Performance
    def _answer_recent_performance(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        sessions = self.retrieve_sessions_for_query(structured)
        if not sessions:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        sids = [str(s.session_id or s.id) for s in sessions]
        kd_values = [s.kd_ratio for s in sessions if s.kd_ratio is not None]
        avg_kd = sum(kd_values) / len(kd_values) if kd_values else None

        wins = sum(1 for s in sessions if s.result and s.result.lower().startswith("win"))
        win_rate = (wins / len(sessions)) * 100

        sess_phrase = f"Session #{sids[0]}" if len(sids) == 1 else f"Sessions {', '.join('#' + x for x in sids)}"
        stats_parts = []
        if avg_kd is not None:
            stats_parts.append(f"average {avg_kd:.2f} K/D")
        stats_parts.append(f"{win_rate:.0f}% win rate ({wins}/{len(sessions)} wins)")

        answer = f"Across your recent {len(sessions)} recorded session{'s' if len(sessions) > 1 else ''} ({sess_phrase}), you maintained an {', '.join(stats_parts)}."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=sids,
            evidence_sessions=[s.model_dump() for s in sessions],
            metrics_used={"average_kd": avg_kd, "win_rate_percent": win_rate, "session_count": len(sessions)},
            status="answered"
        )

    # 4. Map Performance
    def _answer_map_performance(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        all_sessions = self.storage.get_recent_sessions(limit=100)
        sessions_with_map = [s for s in all_sessions if s.map]

        if not sessions_with_map:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        target_map = structured.target_entity or structured.filters.get("map")

        if target_map:
            matching = [s for s in sessions_with_map if s.map.lower() == target_map.lower()]
            if not matching:
                return NaturalLanguageSearchResponse(
                    query=query_text,
                    structured_query=structured,
                    answer=NOT_ENOUGH_DATA,
                    evidence_session_ids=[],
                    evidence_sessions=[],
                    metrics_used={},
                    status="insufficient_data"
                )

            sids = [str(s.session_id or s.id) for s in matching]
            kd_vals = [s.kd_ratio for s in matching if s.kd_ratio is not None]
            avg_kd = sum(kd_vals) / len(kd_vals) if kd_vals else 0.0
            wins = sum(1 for s in matching if s.result and s.result.lower().startswith("win"))
            win_pct = (wins / len(matching)) * 100

            evidence_str = f"Session #{sids[0]}" if len(sids) == 1 else f"Sessions {', '.join('#' + x for x in sids)}"
            answer = f"On {target_map}, you averaged a {avg_kd:.2f} K/D with a {win_pct:.0f}% win rate across {len(matching)} session{'s' if len(matching) > 1 else ''} ({evidence_str})."

            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=answer,
                evidence_session_ids=sids,
                evidence_sessions=[s.model_dump() for s in matching],
                metrics_used={"map": target_map, "average_kd": avg_kd, "session_count": len(matching)},
                status="answered"
            )

        # General: Find top map
        map_groups: Dict[str, List[Session]] = {}
        for s in sessions_with_map:
            map_groups.setdefault(s.map, []).append(s)

        map_stats = []
        for map_name, s_list in map_groups.items():
            kd_vals = [s.kd_ratio for s in s_list if s.kd_ratio is not None]
            avg_kd = sum(kd_vals) / len(kd_vals) if kd_vals else 0.0
            wins = sum(1 for s in s_list if s.result and s.result.lower().startswith("win"))
            map_stats.append({
                "map": map_name,
                "sessions": s_list,
                "avg_kd": avg_kd,
                "wins": wins,
                "win_pct": (wins / len(s_list)) * 100
            })

        map_stats.sort(key=lambda x: (x["avg_kd"], len(x["sessions"])), reverse=True)
        top = map_stats[0]
        sids = [str(s.session_id or s.id) for s in top["sessions"]]
        evidence_str = f"Session #{sids[0]}" if len(sids) == 1 else f"Sessions {', '.join('#' + x for x in sids)}"

        answer = f"You perform best on {top['map']} with an average {top['avg_kd']:.2f} K/D across {len(top['sessions'])} session{'s' if len(top['sessions']) > 1 else ''} ({evidence_str})."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=sids,
            evidence_sessions=[s.model_dump() for s in top["sessions"]],
            metrics_used={"best_map": top["map"], "average_kd": top["avg_kd"], "session_count": len(top["sessions"])},
            status="answered"
        )

    # 5. Configuration Performance
    def _answer_configuration_performance(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        all_sessions = self.storage.get_recent_sessions(limit=100)
        sessions_with_cfg = [s for s in all_sessions if s.configuration]

        if not sessions_with_cfg:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        # Helper to normalize config
        def get_cfg_name(s: Session) -> str:
            if isinstance(s.configuration, dict):
                w = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
                return f"{w} configuration" if w else "Custom loadout"
            return str(s.configuration).strip()

        target_cfg = structured.target_entity or structured.filters.get("configuration")

        if target_cfg:
            matching = [s for s in sessions_with_cfg if target_cfg.lower() in get_cfg_name(s).lower()]
            if not matching:
                return NaturalLanguageSearchResponse(
                    query=query_text,
                    structured_query=structured,
                    answer=NOT_ENOUGH_DATA,
                    evidence_session_ids=[],
                    evidence_sessions=[],
                    metrics_used={},
                    status="insufficient_data"
                )
            sids = [str(s.session_id or s.id) for s in matching]
            kd_vals = [s.kd_ratio for s in matching if s.kd_ratio is not None]
            avg_kd = sum(kd_vals) / len(kd_vals) if kd_vals else 0.0
            evidence_str = f"Session #{sids[0]}" if len(sids) == 1 else f"Sessions {', '.join('#' + x for x in sids)}"

            answer = f"With {target_cfg}, you achieved an average {avg_kd:.2f} K/D across {len(matching)} session{'s' if len(matching) > 1 else ''} ({evidence_str})."

            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=answer,
                evidence_session_ids=sids,
                evidence_sessions=[s.model_dump() for s in matching],
                metrics_used={"configuration": target_cfg, "average_kd": avg_kd, "session_count": len(matching)},
                status="answered"
            )

        # General: Find top configuration
        cfg_groups: Dict[str, List[Session]] = {}
        for s in sessions_with_cfg:
            cfg_name = get_cfg_name(s)
            cfg_groups.setdefault(cfg_name, []).append(s)

        cfg_stats = []
        for cfg_name, s_list in cfg_groups.items():
            kd_vals = [s.kd_ratio for s in s_list if s.kd_ratio is not None]
            avg_kd = sum(kd_vals) / len(kd_vals) if kd_vals else 0.0
            cfg_stats.append({
                "config": cfg_name,
                "sessions": s_list,
                "avg_kd": avg_kd
            })

        cfg_stats.sort(key=lambda x: (x["avg_kd"], len(x["sessions"])), reverse=True)
        top = cfg_stats[0]
        sids = [str(s.session_id or s.id) for s in top["sessions"]]
        evidence_str = f"Session #{sids[0]}" if len(sids) == 1 else f"Sessions {', '.join('#' + x for x in sids)}"

        answer = f"You perform best with {top['config']}, achieving an average {top['avg_kd']:.2f} K/D across {len(top['sessions'])} session{'s' if len(top['sessions']) > 1 else ''} ({evidence_str})."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=sids,
            evidence_sessions=[s.model_dump() for s in top["sessions"]],
            metrics_used={"best_configuration": top["config"], "average_kd": top["avg_kd"], "session_count": len(top["sessions"])},
            status="answered"
        )

    # 6. Improvement
    def _answer_improvement(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        all_sessions = self.storage.get_recent_sessions(limit=100)
        # Reverse to chronological order
        chronological = list(reversed(all_sessions))
        valid_sessions = [s for s in chronological if s.kd_ratio is not None]

        # REQUIREMENT: Must have at least 2 sessions to evaluate improvement
        if len(valid_sessions) < 2:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        mid = len(valid_sessions) // 2
        early_half = valid_sessions[:mid]
        recent_half = valid_sessions[mid:]

        early_avg = sum(s.kd_ratio for s in early_half) / len(early_half)
        recent_avg = sum(s.kd_ratio for s in recent_half) / len(recent_half)
        diff = recent_avg - early_avg

        all_sids = [str(s.session_id or s.id) for s in valid_sessions]
        recent_sids = [str(s.session_id or s.id) for s in recent_half]

        if diff > 0.05:
            answer = f"Yes, you are improving! Your average K/D increased from {early_avg:.2f} in earlier sessions to {recent_avg:.2f} in your recent sessions (+{diff:.2f} K/D improvement)."
        elif diff < -0.05:
            answer = f"Your performance has dipped recently. Your average K/D changed from {early_avg:.2f} in earlier sessions to {recent_avg:.2f} in recent sessions ({diff:.2f} K/D difference)."
        else:
            answer = f"Your performance is consistent. Your average K/D remained steady at ~{recent_avg:.2f} across your recent sessions."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=all_sids,
            evidence_sessions=[s.model_dump() for s in valid_sessions],
            metrics_used={"early_average_kd": early_avg, "recent_average_kd": recent_avg, "kd_diff": diff},
            status="answered"
        )

    # 7. Session Duration
    def _answer_session_duration(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        all_sessions = self.storage.get_recent_sessions(limit=100)
        sessions_with_dur = []
        for s in all_sessions:
            dur = None
            if isinstance(s.duration, (int, float)):
                dur = int(s.duration)
            elif isinstance(s.duration, str):
                digits = "".join([c for c in s.duration if c.isdigit()])
                if digits:
                    dur = int(digits)
            if dur is not None:
                sessions_with_dur.append((s, dur))

        if not sessions_with_dur:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        sids = [str(s.session_id or s.id) for s, _ in sessions_with_dur]
        avg_dur = int(round(sum(dur for _, dur in sessions_with_dur) / len(sessions_with_dur)))

        # Compare < 90m vs >= 90m
        under_90 = [(s, dur) for s, dur in sessions_with_dur if dur < 90 and s.kd_ratio is not None]
        over_90 = [(s, dur) for s, dur in sessions_with_dur if dur >= 90 and s.kd_ratio is not None]

        if under_90 and (len(under_90) + len(over_90) >= 2):
            under_avg_kd = sum(s.kd_ratio for s, _ in under_90) / len(under_90)
            if over_90:
                over_avg_kd = sum(s.kd_ratio for s, _ in over_90) / len(over_90)
                if under_avg_kd > over_avg_kd:
                    answer = f"Your average session duration is {avg_dur} minutes. You perform noticeably better during sessions under 90 minutes (average {under_avg_kd:.2f} K/D across {len(under_90)} sessions) compared to longer sessions ({over_avg_kd:.2f} K/D)."
                else:
                    answer = f"Your average session duration is {avg_dur} minutes across {len(sessions_with_dur)} recorded sessions."
            else:
                answer = f"Your average session duration is {avg_dur} minutes. In sessions under 90 minutes, you maintained an average {under_avg_kd:.2f} K/D."
        else:
            answer = f"Your recorded gaming sessions average {avg_dur} minutes in duration across {len(sessions_with_dur)} sessions."

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=sids,
            evidence_sessions=[s.model_dump() for s, _ in sessions_with_dur],
            metrics_used={"average_duration_minutes": avg_dur, "session_count": len(sessions_with_dur)},
            status="answered"
        )

    # 8. Performance Comparison
    def _answer_performance_comparison(self, query_text: str, structured: StructuredQuery) -> NaturalLanguageSearchResponse:
        all_sessions = self.storage.get_recent_sessions(limit=100)
        session_id_matches = extract_session_ids(query_text)

        # Subcase A: Compare two explicitly named sessions (e.g. Session #18 vs Session #14)
        if len(session_id_matches) >= 2:
            id1, id2 = session_id_matches[0], session_id_matches[1]
            s1 = self.storage.get_session_by_id(id1)
            s2 = self.storage.get_session_by_id(id2)

            if not s1 or not s2:
                return NaturalLanguageSearchResponse(
                    query=query_text,
                    structured_query=structured,
                    answer=NOT_ENOUGH_DATA,
                    evidence_session_ids=[],
                    evidence_sessions=[],
                    metrics_used={},
                    status="insufficient_data"
                )

            kd1 = s1.kd_ratio or 0.0
            kd2 = s2.kd_ratio or 0.0
            diff = kd1 - kd2

            answer = (
                f"Comparing Session #{id1} and Session #{id2}: "
                f"In Session #{id1}, you recorded a {kd1:.1f} K/D ({s1.result or 'No outcome'}) "
                f"versus Session #{id2} with a {kd2:.1f} K/D ({s2.result or 'No outcome'}) "
                f"({diff:+.2f} K/D difference)."
            )

            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=answer,
                evidence_session_ids=[str(id1), str(id2)],
                evidence_sessions=[s1.model_dump(), s2.model_dump()],
                metrics_used={"session_1_kd": kd1, "session_2_kd": kd2, "diff": diff},
                status="answered"
            )

        # Subcase B: Compare latest session to historical average
        if len(all_sessions) < 2:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        latest = all_sessions[0]
        history = all_sessions[1:]
        hist_kds = [s.kd_ratio for s in history if s.kd_ratio is not None]

        if latest.kd_ratio is None or not hist_kds:
            return NaturalLanguageSearchResponse(
                query=query_text,
                structured_query=structured,
                answer=NOT_ENOUGH_DATA,
                evidence_session_ids=[],
                evidence_sessions=[],
                metrics_used={},
                status="insufficient_data"
            )

        hist_avg = sum(hist_kds) / len(hist_kds)
        diff = latest.kd_ratio - hist_avg
        latest_sid = str(latest.session_id or latest.id)

        answer = (
            f"In your latest Session #{latest_sid}, you recorded a {latest.kd_ratio:.2f} K/D ({latest.result or 'Result recorded'}), "
            f"which is {'higher' if diff >= 0 else 'lower'} than your prior baseline average of {hist_avg:.2f} K/D ({diff:+.2f} difference)."
        )

        evidence_sids = [latest_sid] + [str(s.session_id or s.id) for s in history[:3]]

        return NaturalLanguageSearchResponse(
            query=query_text,
            structured_query=structured,
            answer=answer,
            evidence_session_ids=evidence_sids,
            evidence_sessions=[latest.model_dump()] + [s.model_dump() for s in history[:3]],
            metrics_used={"latest_kd": latest.kd_ratio, "historical_avg_kd": hist_avg, "diff": diff},
            status="answered"
        )


# Default singleton instance
default_nl_search_engine = NaturalLanguageSearchEngine()
