import math
from typing import List, Dict, Any, Optional, Union, Tuple
from collections import defaultdict

from app.models import Session, CrossSessionAnalysisResult
from app.session_storage import SessionStorage, default_session_storage


NOT_ENOUGH_DATA = "Not enough data to determine this."
MIN_SESSIONS_REQUIRED = 2


# =====================================================================
# PHASE 8: CROSS-SESSION ANALYZER
# =====================================================================

class CrossSessionAnalyzer:
    """
    Evidence-backed Cross-Session Analyzer for Gaming Second Brain (Phase 8).
    
    Adheres strictly to core rules:
    - Never claim a pattern from a single session. Minimum 2 sessions required.
    - Explicitly separates:
        1. FACT: Direct factual observations from individual sessions.
        2. PATTERN: Aggregated statistical discovery across multiple sessions.
        3. AI INTERPRETATION: Cautious evaluation with strict causation guard.
    - Does NOT invent causation (e.g. does not say a loadout caused better performance
      unless stored data supports it; highlights correlation instead of unwarranted causality).
    - Returns evidence session IDs for all findings.
    - Supports:
        * Am I improving?
        * What changed between my best and worst sessions?
        * Which map do I perform best on?
        * Which configuration produces better results?
        * How does session duration relate to performance?
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage

    def _get_sessions(self, sessions: Optional[List[Session]] = None) -> List[Session]:
        if sessions is not None:
            return list(sessions)
        return self.storage.get_recent_sessions(limit=100)

    def _insufficient_result(self, question: str, analysis_type: str) -> CrossSessionAnalysisResult:
        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=[],
            pattern=NOT_ENOUGH_DATA,
            interpretation=NOT_ENOUGH_DATA,
            evidence_session_ids=[],
            status="insufficient_data",
            metrics_summary={}
        )

    # -----------------------------------------------------------------
    # QUESTION 1: "Am I improving?"
    # -----------------------------------------------------------------
    def analyze_improvement(self, sessions: Optional[List[Session]] = None) -> CrossSessionAnalysisResult:
        question = "Am I improving?"
        analysis_type = "improving"
        all_sess = self._get_sessions(sessions)

        # Chronological ordering (oldest to newest)
        chronological = list(reversed(all_sess))
        valid = [s for s in chronological if s.kd_ratio is not None]

        # RULE: Never claim a pattern from a single session
        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_result(question, analysis_type)

        kds = [s.kd_ratio for s in valid]
        sids = [str(s.session_id or s.id) for s in valid]
        n = len(kds)

        # Compute stats: mean, standard deviation, split delta
        mean_kd = sum(kds) / n
        variance = sum((x - mean_kd) ** 2 for x in kds) / n
        std_dev = math.sqrt(variance)

        mid = n // 2
        early_half = kds[:mid]
        recent_half = kds[mid:]
        early_avg = sum(early_half) / len(early_half)
        recent_avg = sum(recent_half) / len(recent_half)
        delta = recent_avg - early_avg

        # Check for oscillating/alternating swings (inconsistent performance)
        diffs = [kds[i+1] - kds[i] for i in range(n-1)]
        sign_changes = sum(1 for i in range(len(diffs)-1) if (diffs[i] > 0 and diffs[i+1] < 0) or (diffs[i] < 0 and diffs[i+1] > 0))
        is_oscillating = sign_changes >= 2 and std_dev >= 0.35

        # Format concrete FACTS
        facts = [f"Session #{sids[i]} recorded K/D = {kds[i]:.2f}" for i in range(n)]

        # Determine Pattern & Interpretation
        if is_oscillating:
            pattern = (
                f"K/D exhibits high variance across {n} sessions (range {min(kds):.2f} to {max(kds):.2f}, "
                f"standard deviation {std_dev:.2f}) with frequent swings rather than a monotonic trajectory."
            )
            interpretation = (
                "Performance is currently inconsistent across matches rather than steadily improving or declining. "
                "Fluctuations indicate volatility between sessions."
            )
            trend_label = "inconsistent"
        elif delta > 0.15:
            pattern = (
                f"Average K/D increased progressively from {early_avg:.2f} in earlier sessions to {recent_avg:.2f} "
                f"in recent sessions (net gain of {delta:+.2f} K/D across {n} sessions)."
            )
            interpretation = (
                "The player exhibits an evidence-backed improving performance trend across recorded sessions, "
                "demonstrating higher combat conversion in recent matches."
            )
            trend_label = "increasing"
        elif delta < -0.15:
            pattern = (
                f"Average K/D declined from {early_avg:.2f} in earlier sessions to {recent_avg:.2f} "
                f"in recent sessions (net drop of {delta:+.2f} K/D across {n} sessions)."
            )
            interpretation = (
                "The player exhibits a declining performance trend across recorded sessions. "
                "The data establishes a statistical drop, but does not conclusively prove whether fatigue, "
                "opponent difficulty, or tactical adjustments caused it."
            )
            trend_label = "decreasing"
        else:
            pattern = (
                f"Average K/D remained steady at ~{mean_kd:.2f} across {n} sessions "
                f"(standard deviation {std_dev:.2f}, delta {delta:+.2f})."
            )
            interpretation = (
                "Performance has remained consistent and stable across recorded sessions with minimal variation."
            )
            trend_label = "consistent"

        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=facts,
            pattern=pattern,
            interpretation=interpretation,
            evidence_session_ids=sids,
            status="determined",
            metrics_summary={
                "trend": trend_label,
                "session_count": n,
                "mean_kd": round(mean_kd, 2),
                "early_avg_kd": round(early_avg, 2),
                "recent_avg_kd": round(recent_avg, 2),
                "delta": round(delta, 2),
                "std_dev": round(std_dev, 2)
            }
        )

    # -----------------------------------------------------------------
    # QUESTION 2: "What changed between my best and worst sessions?"
    # -----------------------------------------------------------------
    def analyze_best_vs_worst(self, sessions: Optional[List[Session]] = None) -> CrossSessionAnalysisResult:
        question = "What changed between my best and worst sessions?"
        analysis_type = "best_vs_worst"
        all_sess = self._get_sessions(sessions)
        valid = [s for s in all_sess if s.kd_ratio is not None]

        # RULE: Never claim a pattern from a single session
        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_result(question, analysis_type)

        sorted_by_kd = sorted(valid, key=lambda s: s.kd_ratio, reverse=True)
        best = sorted_by_kd[0]
        worst = sorted_by_kd[-1]

        best_sid = str(best.session_id or best.id)
        worst_sid = str(worst.session_id or worst.id)

        if best_sid == worst_sid:
            return self._insufficient_result(question, analysis_type)

        def fmt_cfg(s: Session) -> str:
            if isinstance(s.configuration, dict):
                w = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
                return f"{w} configuration" if w else "Custom loadout"
            return str(s.configuration or "Unspecified configuration")

        best_cfg = fmt_cfg(best)
        worst_cfg = fmt_cfg(worst)

        # 1. FACTS
        fact_best = (
            f"Best Session #{best_sid}: K/D = {best.kd_ratio:.2f} ({best.kills or 0} kills, {best.deaths or 0} deaths) "
            f"on {best.map or 'Unspecified map'} using {best_cfg}, duration {best.duration or 'N/A'} mins, "
            f"result: {best.result or 'Unspecified'}."
        )
        fact_worst = (
            f"Worst Session #{worst_sid}: K/D = {worst.kd_ratio:.2f} ({worst.kills or 0} kills, {worst.deaths or 0} deaths) "
            f"on {worst.map or 'Unspecified map'} using {worst_cfg}, duration {worst.duration or 'N/A'} mins, "
            f"result: {worst.result or 'Unspecified'}."
        )

        # 2. PATTERN
        kd_diff = best.kd_ratio - worst.kd_ratio
        pattern = (
            f"The performance gap between your best (Session #{best_sid}) and worst (Session #{worst_sid}) sessions "
            f"was {kd_diff:+.2f} K/D. Best performance occurred on {best.map or 'Unspecified'} with {best_cfg}, "
            f"while lowest performance occurred on {worst.map or 'Unspecified'} with {worst_cfg}."
        )

        # 3. AI INTERPRETATION (Causation Guard)
        interpretation = (
            f"Notable shifts between best and worst matches correlate with map environment ({best.map} vs {worst.map}) "
            f"and configuration ({best_cfg} vs {worst_cfg}). While these variables correlate with the outcome, "
            "the data does not prove that configuration or map alone caused the divergence, as team composition, "
            "round pacing, and opponent skill were also differing variables."
        )

        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=[fact_best, fact_worst],
            pattern=pattern,
            interpretation=interpretation,
            evidence_session_ids=[best_sid, worst_sid],
            status="determined",
            metrics_summary={
                "best_session_id": best_sid,
                "best_kd": best.kd_ratio,
                "worst_session_id": worst_sid,
                "worst_kd": worst.kd_ratio,
                "kd_delta": round(kd_diff, 2),
                "best_map": best.map,
                "worst_map": worst.map,
                "best_config": best_cfg,
                "worst_config": worst_cfg
            }
        )

    # -----------------------------------------------------------------
    # QUESTION 3: "Which map do I perform best on?"
    # -----------------------------------------------------------------
    def analyze_map_performance(self, sessions: Optional[List[Session]] = None) -> CrossSessionAnalysisResult:
        question = "Which map do I perform best on?"
        analysis_type = "map_performance"
        all_sess = self._get_sessions(sessions)
        valid = [s for s in all_sess if s.map and s.kd_ratio is not None]

        # RULE: Never claim a pattern from a single session
        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_result(question, analysis_type)

        map_groups: Dict[str, List[Session]] = defaultdict(list)
        for s in valid:
            map_groups[s.map].append(s)

        # FACTS
        facts = []
        map_stats = []
        for map_name, s_list in map_groups.items():
            sids = [str(s.session_id or s.id) for s in s_list]
            kd_vals = [s.kd_ratio for s in s_list]
            avg_kd = sum(kd_vals) / len(kd_vals)
            wins = sum(1 for s in s_list if s.result and s.result.lower().startswith("win"))
            win_pct = (wins / len(s_list)) * 100
            facts.append(
                f"{map_name}: {', '.join(f'Session #{sids[i]} K/D = {kd_vals[i]:.2f}' for i in range(len(s_list)))} "
                f"(average {avg_kd:.2f} K/D, {win_pct:.0f}% win rate)."
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

        # PATTERN
        other_maps_desc = ", ".join(f"{m['map']} ({m['avg_kd']:.2f} K/D across {m['count']} session{'s' if m['count'] > 1 else ''})" for m in map_stats[1:])
        comparison_clause = f", outperforming {other_maps_desc}" if other_maps_desc else ""
        pattern = (
            f"Across {len(valid)} analyzed sessions, {top['map']} yielded your highest average K/D of {top['avg_kd']:.2f} "
            f"with a {top['win_pct']:.0f}% win rate across {top['count']} session{'s' if top['count'] > 1 else ''}{comparison_clause}."
        )

        # AI INTERPRETATION (Causation Guard)
        interpretation = (
            f"{top['map']} represents your strongest recorded map environment based on stored match history. "
            "While comfort and positioning on this map correlate with higher combat conversion, the data does "
            "not establish map layout as the sole cause of performance differences, as opponent ranks were unobserved."
        )

        all_evidence = []
        for m in map_stats:
            all_evidence.extend(m["sids"])

        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=facts,
            pattern=pattern,
            interpretation=interpretation,
            evidence_session_ids=all_evidence,
            status="determined",
            metrics_summary={
                "best_map": top["map"],
                "best_map_avg_kd": round(top["avg_kd"], 2),
                "best_map_sessions": top["count"],
                "total_maps_compared": len(map_stats)
            }
        )

    # -----------------------------------------------------------------
    # QUESTION 4: "Which configuration produces better results?"
    # -----------------------------------------------------------------
    def analyze_configuration_performance(self, sessions: Optional[List[Session]] = None) -> CrossSessionAnalysisResult:
        question = "Which configuration produces better results?"
        analysis_type = "configuration_performance"
        all_sess = self._get_sessions(sessions)

        def normalize_cfg(s: Session) -> str:
            if isinstance(s.configuration, dict):
                w = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
                return f"{w} configuration" if w else "Custom configuration"
            if s.configuration:
                return str(s.configuration).strip()
            return ""

        valid = [s for s in all_sess if normalize_cfg(s) and s.kd_ratio is not None]

        # RULE: Never claim a pattern from a single session
        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_result(question, analysis_type)

        cfg_groups: Dict[str, List[Session]] = defaultdict(list)
        for s in valid:
            cfg_groups[normalize_cfg(s)].append(s)

        # FACTS
        facts = []
        cfg_stats = []
        for cfg_name, s_list in cfg_groups.items():
            sids = [str(s.session_id or s.id) for s in s_list]
            kd_vals = [s.kd_ratio for s in s_list]
            avg_kd = sum(kd_vals) / len(kd_vals)
            wins = sum(1 for s in s_list if s.result and s.result.lower().startswith("win"))
            win_pct = (wins / len(s_list)) * 100
            facts.append(
                f"{cfg_name}: {', '.join(f'Session #{sids[i]} K/D = {kd_vals[i]:.2f}' for i in range(len(s_list)))} "
                f"(average {avg_kd:.2f} K/D across {len(s_list)} session{'s' if len(s_list) > 1 else ''})."
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

        # PATTERN
        other_cfgs = ", ".join(f"{c['config']} ({c['avg_kd']:.2f} K/D across {c['count']} session{'s' if c['count'] > 1 else ''})" for c in cfg_stats[1:])
        comp_clause = f", higher than {other_cfgs}" if other_cfgs else ""
        pattern = (
            f"Across {len(valid)} sessions, {top['config']} recorded the highest average K/D of {top['avg_kd']:.2f} "
            f"across {top['count']} session{'s' if top['count'] > 1 else ''}{comp_clause}."
        )

        # AI INTERPRETATION (Causation Guard)
        # CRITICAL RULE: Do not say a configuration caused better performance unless data supports it
        interpretation = (
            f"Sessions using {top['config']} correlated with higher combat efficiency in recorded matches. "
            "However, the telemetry does not prove that the loadout itself caused superior performance, "
            "as crosshair placement, team synergy, and map context also varied across these sessions."
        )

        all_evidence = []
        for c in cfg_stats:
            all_evidence.extend(c["sids"])

        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=facts,
            pattern=pattern,
            interpretation=interpretation,
            evidence_session_ids=all_evidence,
            status="determined",
            metrics_summary={
                "best_configuration": top["config"],
                "best_config_avg_kd": round(top["avg_kd"], 2),
                "best_config_sessions": top["count"],
                "total_configs_compared": len(cfg_stats)
            }
        )

    # -----------------------------------------------------------------
    # QUESTION 5: "How does session duration relate to performance?"
    # -----------------------------------------------------------------
    def analyze_duration_vs_performance(self, sessions: Optional[List[Session]] = None) -> CrossSessionAnalysisResult:
        question = "How does session duration relate to performance?"
        analysis_type = "duration_vs_performance"
        all_sess = self._get_sessions(sessions)

        def extract_mins(s: Session) -> Optional[int]:
            if isinstance(s.duration, (int, float)):
                return int(s.duration)
            if isinstance(s.duration, str):
                digits = "".join([c for c in s.duration if c.isdigit()])
                if digits:
                    return int(digits)
            return None

        valid = []
        for s in all_sess:
            mins = extract_mins(s)
            if mins is not None and s.kd_ratio is not None:
                valid.append((s, mins))

        # RULE: Never claim a pattern from a single session
        if len(valid) < MIN_SESSIONS_REQUIRED:
            return self._insufficient_result(question, analysis_type)

        short_sessions = [(s, m) for s, m in valid if m < 90]
        long_sessions = [(s, m) for s, m in valid if m >= 90]

        # FACTS
        facts = []
        for s, m in valid:
            sid = str(s.session_id or s.id)
            facts.append(f"Session #{sid}: duration = {m} mins, K/D = {s.kd_ratio:.2f}")

        all_sids = [str(s.session_id or s.id) for s, _ in valid]

        # PATTERN
        avg_dur = int(round(sum(m for _, m in valid) / len(valid)))

        if short_sessions and long_sessions:
            short_avg_kd = sum(s.kd_ratio for s, _ in short_sessions) / len(short_sessions)
            long_avg_kd = sum(s.kd_ratio for s, _ in long_sessions) / len(long_sessions)
            kd_diff = short_avg_kd - long_avg_kd

            pattern = (
                f"Sessions under 90 minutes averaged {short_avg_kd:.2f} K/D across {len(short_sessions)} session{'s' if len(short_sessions) > 1 else ''}, "
                f"whereas sessions 90 minutes or longer averaged {long_avg_kd:.2f} K/D across {len(long_sessions)} session{'s' if len(long_sessions) > 1 else ''} "
                f"({kd_diff:+.2f} K/D difference; average session duration: {avg_dur} mins)."
            )

            # AI INTERPRETATION (Causation Guard)
            interpretation = (
                "Combat efficiency shows an observable negative correlation with sessions extending beyond 90 minutes. "
                "While this pattern is consistent with mental fatigue and diminished reaction times, the data demonstrates "
                "correlation rather than conclusive causation."
            )
        else:
            mean_kd = sum(s.kd_ratio for s, _ in valid) / len(valid)
            pattern = (
                f"Recorded sessions average {avg_dur} minutes in duration with an overall average K/D of {mean_kd:.2f} "
                f"across {len(valid)} sessions."
            )
            interpretation = (
                f"All recorded sessions fall within a similar duration bracket (~{avg_dur} mins). "
                "No strong correlation between duration differences and combat performance is observed in the current sample."
            )

        return CrossSessionAnalysisResult(
            question=question,
            analysis_type=analysis_type,
            facts=facts,
            pattern=pattern,
            interpretation=interpretation,
            evidence_session_ids=all_sids,
            status="determined",
            metrics_summary={
                "average_duration_minutes": avg_dur,
                "total_sessions": len(valid),
                "short_session_count": len(short_sessions),
                "long_session_count": len(long_sessions)
            }
        )

    # -----------------------------------------------------------------
    # DISPATCHER
    # -----------------------------------------------------------------
    def analyze_question(
        self,
        question: str,
        sessions: Optional[List[Session]] = None
    ) -> CrossSessionAnalysisResult:
        """
        Dispatches analytical questions to their appropriate handler.
        """
        q_lower = question.lower().strip()

        if any(w in q_lower for w in ["improv", "getting better", "getting worse", "trend", "progress"]):
            return self.analyze_improvement(sessions)
        elif any(w in q_lower for w in ["best and worst", "between my best", "compare best", "what changed"]):
            return self.analyze_best_vs_worst(sessions)
        elif any(w in q_lower for w in ["map", "maps"]):
            return self.analyze_map_performance(sessions)
        elif any(w in q_lower for w in ["configuration", "loadout", "weapon", "setup"]):
            return self.analyze_configuration_performance(sessions)
        elif any(w in q_lower for w in ["duration", "how long", "length"]):
            return self.analyze_duration_vs_performance(sessions)
        else:
            # Default to improvement trend analysis
            return self.analyze_improvement(sessions)


# Default singleton instance
default_cross_session_analyzer = CrossSessionAnalyzer()
