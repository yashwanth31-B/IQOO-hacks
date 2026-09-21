"""
Phase 10: Performance Pattern Engine.

Analyzes stored sessions and identifies repeated patterns.
Supported patterns:
- repeated deaths
- repeated map problems
- repeated positioning issues
- configuration correlations
- session-duration patterns
- performance consistency
- recurring successful actions
- recurring unsuccessful actions

Strict rules:
1. Never call something a pattern based on one session. Require multiple relevant observations (minimum 2).
2. Separate:
   FACT
   PATTERN
   INTERPRETATION
3. Do not claim why the player died unless stored data establishes it.
4. Every pattern must contain evidence_session_ids.
"""

from typing import List, Dict, Any, Optional, Union, Tuple
from collections import defaultdict
import uuid
import re

from app.models import (
    Session,
    PerformancePattern,
    PerformancePatternResponse
)
from app.session_storage import SessionStorage, default_session_storage


MIN_SESSIONS_REQUIRED = 2


class PerformancePatternEngine:
    """
    Phase 10: Performance Pattern Engine.
    Discovers evidence-backed recurring performance patterns across multiple stored sessions.
    Strictly adheres to:
    - Never identifying a pattern from 1 session.
    - Explicitly separating FACT, PATTERN, and INTERPRETATION.
    - Grounding all observations in evidence_session_ids.
    - Preventing unsupported causal claims.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage

    def analyze_patterns(
        self,
        game: Optional[str] = None,
        pattern_type: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> PerformancePatternResponse:
        """
        Analyzes stored sessions to discover repeated patterns.
        Requires >= 2 sessions before identifying any pattern.
        """
        # 1. Retrieve sessions
        if sessions is not None:
            all_sessions = list(sessions)
        else:
            all_sessions = self.storage.get_recent_sessions(limit=100)

        # 2. Filter by game if provided
        if game:
            filtered_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
        else:
            filtered_sessions = all_sessions

        # STRICT INVARIANT: Never call something a pattern based on one session
        if len(filtered_sessions) < MIN_SESSIONS_REQUIRED:
            return PerformancePatternResponse(
                patterns=[],
                total_patterns=0,
                status="insufficient_data",
                message="Not enough data to identify patterns. Minimum 2 sessions required.",
                evidence_session_ids=[]
            )

        patterns: List[PerformancePattern] = []

        # -------------------------------------------------------------
        # 1. REPEATED DEATHS
        # -------------------------------------------------------------
        # Scan death locations mentioned in timeline or player notes
        location_deaths: Dict[str, List[Union[str, int]]] = defaultdict(list)
        common_locations = [
            "c long", "pochinki", "b main", "a site", "b site", "heaven",
            "school", "bridge", "mid", "water", "corridor", "garage"
        ]

        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            text_to_search = (s.player_notes or "").lower()
            if s.timeline:
                text_to_search += " " + " ".join((e.description or "").lower() for e in s.timeline if e.event_type == "death")

            for loc in common_locations:
                if loc in text_to_search:
                    if sid not in location_deaths[loc]:
                        location_deaths[loc].append(sid)

        for loc, sids in location_deaths.items():
            if len(sids) >= 2:
                count_str = "three" if len(sids) == 3 else ("two" if len(sids) == 2 else str(len(sids)))
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-deaths-{uuid.uuid4().hex[:6]}",
                    pattern_type="repeated_deaths",
                    game=game or filtered_sessions[0].game,
                    fact=f"Player died at similar locations in {count_str} recorded sessions.",
                    pattern="Repeated deaths occurred in similar areas.",
                    interpretation="These locations may deserve review.",
                    evidence_session_ids=sids
                ))
                break  # Primary location pattern

        # -------------------------------------------------------------
        # 2. REPEATED MAP PROBLEMS
        # -------------------------------------------------------------
        map_sessions: Dict[str, List[Session]] = defaultdict(list)
        for s in filtered_sessions:
            m = s.map or s.map_or_level
            if m:
                map_sessions[m].append(s)

        for map_name, ms_list in map_sessions.items():
            if len(ms_list) >= 2:
                losses = [s for s in ms_list if (s.result or s.outcome or "").lower() in ["defeat", "loss", "lost"]]
                if len(losses) >= 2:
                    sids = [s.session_id or s.id for s in losses]
                    patterns.append(PerformancePattern(
                        pattern_id=f"pat-map-{uuid.uuid4().hex[:6]}",
                        pattern_type="repeated_map_problems",
                        game=game or filtered_sessions[0].game,
                        fact=f"Recorded {len(losses)} defeats across {len(ms_list)} sessions on {map_name}.",
                        pattern=f"Repeated difficulties converting matches to victories on {map_name}.",
                        interpretation=f"Map-specific choke points and defense setups on {map_name} may benefit from review.",
                        evidence_session_ids=sids
                    ))
                    break

        # -------------------------------------------------------------
        # 3. REPEATED POSITIONING ISSUES
        # -------------------------------------------------------------
        pos_sids: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            notes = (s.player_notes or "").lower()
            timeline_text = " ".join((e.description or "").lower() for e in (s.timeline or []))
            combined_txt = f"{notes} {timeline_text}"
            if any(term in combined_txt for term in ["positioning", "ego-peek", "ego peek", "bad angle", "exposed", "dry-peek"]):
                pos_sids.append(sid)
                continue
            # Check first_deaths >= 4
            perf = s.performance_metrics or s.stats or {}
            fd = perf.get("first_deaths")
            if fd is not None and isinstance(fd, (int, float)) and fd >= 4:
                pos_sids.append(sid)

        if len(pos_sids) >= 2:
            patterns.append(PerformancePattern(
                pattern_id=f"pat-pos-{uuid.uuid4().hex[:6]}",
                pattern_type="repeated_positioning_issues",
                game=game or filtered_sessions[0].game,
                fact=f"Positioning vulnerabilities and opening deaths were noted in {len(pos_sids)} recorded sessions.",
                pattern="Repeated positioning vulnerabilities occurred during initial round contact.",
                interpretation="Defensive holding angles and peek discipline may warrant tactical adjustment.",
                evidence_session_ids=pos_sids
            ))

        # -------------------------------------------------------------
        # 4. CONFIGURATION CORRELATIONS
        # -------------------------------------------------------------
        config_sessions: Dict[str, List[Session]] = defaultdict(list)
        for s in filtered_sessions:
            cfg = s.configuration or s.character_or_loadout
            if cfg:
                cfg_str = str(cfg).strip()
                config_sessions[cfg_str].append(s)

        # Look for configurations with >= 2 sessions each to compare
        qualifying_configs = [(c, slist) for c, slist in config_sessions.items() if len(slist) >= 2]
        if len(qualifying_configs) >= 2:
            qualifying_configs.sort(
                key=lambda item: sum(s.kd_ratio or 0.0 for s in item[1]) / len(item[1]),
                reverse=True
            )
            top_cfg, top_list = qualifying_configs[0]
            bot_cfg, bot_list = qualifying_configs[-1]
            top_kd = sum(s.kd_ratio or 0.0 for s in top_list) / len(top_list)
            bot_kd = sum(s.kd_ratio or 0.0 for s in bot_list) / len(bot_list)

            if top_kd > bot_kd + 0.3:
                evidence_cfg = [s.session_id or s.id for s in top_list + bot_list]
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-cfg-{uuid.uuid4().hex[:6]}",
                    pattern_type="configuration_correlations",
                    game=game or filtered_sessions[0].game,
                    fact=f"Configuration '{top_cfg}' averaged {top_kd:.2f} K/D across {len(top_list)} sessions, compared to {bot_kd:.2f} K/D with '{bot_cfg}' across {len(bot_list)} sessions.",
                    pattern=f"Higher combat conversion is correlated with '{top_cfg}' over '{bot_cfg}'.",
                    interpretation=f"Performance correlates positively with '{top_cfg}', though map context may also be a factor.",
                    evidence_session_ids=evidence_cfg
                ))

        # -------------------------------------------------------------
        # 5. SESSION DURATION PATTERNS
        # -------------------------------------------------------------
        short_sessions = [s for s in filtered_sessions if (s.duration_mins or (s.duration if isinstance(s.duration, (int, float)) else 0)) <= 60 and (s.kd_ratio is not None)]
        long_sessions = [s for s in filtered_sessions if (s.duration_mins or (s.duration if isinstance(s.duration, (int, float)) else 0)) > 60 and (s.kd_ratio is not None)]

        if len(short_sessions) >= 2 and len(long_sessions) >= 2:
            kd_short = sum(s.kd_ratio for s in short_sessions) / len(short_sessions)
            kd_long = sum(s.kd_ratio for s in long_sessions) / len(long_sessions)
            if kd_short > kd_long + 0.3:
                evidence_dur = [s.session_id or s.id for s in short_sessions + long_sessions]
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-dur-{uuid.uuid4().hex[:6]}",
                    pattern_type="session_duration_patterns",
                    game=game or filtered_sessions[0].game,
                    fact=f"Sessions under 60 minutes averaged {kd_short:.2f} K/D across {len(short_sessions)} matches, while sessions over 60 minutes averaged {kd_long:.2f} K/D across {len(long_sessions)} matches.",
                    pattern="Combat performance tends to decrease during extended continuous sessions.",
                    interpretation="Fatigue and cognitive load during longer play sessions may warrant scheduled breaks.",
                    evidence_session_ids=evidence_dur
                ))

        # -------------------------------------------------------------
        # 6. PERFORMANCE CONSISTENCY
        # -------------------------------------------------------------
        kd_sessions = [s for s in filtered_sessions if s.kd_ratio is not None and (s.session_id or s.id)]
        if len(kd_sessions) >= 3:
            kds = [s.kd_ratio for s in kd_sessions]
            min_kd, max_kd = min(kds), max(kds)
            evidence_con = [s.session_id or s.id for s in kd_sessions]
            if max_kd - min_kd >= 0.8:
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-con-{uuid.uuid4().hex[:6]}",
                    pattern_type="performance_consistency",
                    game=game or filtered_sessions[0].game,
                    fact=f"Session K/D ratios ranged from {min_kd:.1f} to {max_kd:.1f} across {len(kd_sessions)} recorded sessions.",
                    pattern="Combat performance demonstrates high variance across consecutive sessions.",
                    interpretation="Warmup routines and consistent pre-match preparation may help stabilize variance.",
                    evidence_session_ids=evidence_con
                ))
            elif max_kd - min_kd <= 0.4:
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-con-{uuid.uuid4().hex[:6]}",
                    pattern_type="performance_consistency",
                    game=game or filtered_sessions[0].game,
                    fact=f"Session K/D ratios remained within a stable range ({min_kd:.1f} to {max_kd:.1f}) across {len(kd_sessions)} sessions.",
                    pattern="Performance exhibits high consistency across consecutive matches.",
                    interpretation="Tactical fundamentals appear consistently maintained across different opponents.",
                    evidence_session_ids=evidence_con
                ))

        # -------------------------------------------------------------
        # 7. RECURRING SUCCESSFUL ACTIONS
        # -------------------------------------------------------------
        success_actions: Dict[str, List[Union[str, int]]] = defaultdict(list)
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            if s.timeline:
                for ev in s.timeline:
                    if ev.impact == "positive" or ev.event_type == "clutch":
                        action_name = ev.description.strip()
                        # Shorten or normalize action name
                        if "clutch" in action_name.lower():
                            success_actions["post-plant clutch"].append(sid)
                        elif "smoke" in action_name.lower() or "rotation" in action_name.lower():
                            success_actions["smoke rotation"].append(sid)
                        elif "compound" in action_name.lower():
                            success_actions["compound control"].append(sid)

        for action_name, sids in success_actions.items():
            sids_unique = list(dict.fromkeys(sids))
            if len(sids_unique) >= 2:
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-succ-{uuid.uuid4().hex[:6]}",
                    pattern_type="recurring_successful_actions",
                    game=game or filtered_sessions[0].game,
                    fact=f"Successful execution of '{action_name}' was recorded in {len(sids_unique)} separate sessions.",
                    pattern=f"Recurring round success is associated with '{action_name}' executions.",
                    interpretation=f"Continuing to prioritize '{action_name}' reinforces proven high-percentage setups.",
                    evidence_session_ids=sids_unique
                ))
                break

        # -------------------------------------------------------------
        # 8. RECURRING UNSUCCESSFUL ACTIONS
        # -------------------------------------------------------------
        unsuccess_actions: Dict[str, List[Union[str, int]]] = defaultdict(list)
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            notes = (s.player_notes or "").lower()
            timeline_txt = " ".join((e.description or "").lower() for e in (s.timeline or []))
            combined_txt = f"{notes} {timeline_txt}"
            if "dry-peek" in combined_txt or "ego-peek" in combined_txt:
                unsuccess_actions["ego dry-peeking without utility"].append(sid)
            if "panic roll" in combined_txt:
                unsuccess_actions["panic rolling under attack"].append(sid)
            if "bridge" in combined_txt and ("died" in combined_txt or "camped" in combined_txt):
                unsuccess_actions["uncontested bridge crossing attempts"].append(sid)

        for action_name, sids in unsuccess_actions.items():
            sids_unique = list(dict.fromkeys(sids))
            if len(sids_unique) >= 2:
                patterns.append(PerformancePattern(
                    pattern_id=f"pat-unsucc-{uuid.uuid4().hex[:6]}",
                    pattern_type="recurring_unsuccessful_actions",
                    game=game or filtered_sessions[0].game,
                    fact=f"Unsuccessful attempts at '{action_name}' were recorded in {len(sids_unique)} separate sessions.",
                    pattern=f"Repeated negative round outcomes followed '{action_name}'.",
                    interpretation=f"Alternative approaches to '{action_name}' may reduce unforced round deficits.",
                    evidence_session_ids=sids_unique
                ))
                break

        # Filter by pattern_type if requested
        if pattern_type:
            pt_clean = pattern_type.strip().lower()
            patterns = [p for p in patterns if p.pattern_type.lower() == pt_clean]

        if not patterns:
            return PerformancePatternResponse(
                patterns=[],
                total_patterns=0,
                status="insufficient_data",
                message="No recurring patterns identified meeting the minimum observation threshold.",
                evidence_session_ids=[]
            )

        all_evidence = sorted(list({str(sid) for p in patterns for sid in p.evidence_session_ids}))

        return PerformancePatternResponse(
            patterns=patterns,
            total_patterns=len(patterns),
            status="success",
            message="Patterns identified from stored sessions.",
            evidence_session_ids=all_evidence
        )


# Global default engine instance
default_pattern_engine = PerformancePatternEngine()
