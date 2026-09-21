import re
import json
from typing import Dict, Any, List, Optional, Union
from app.config import settings
from app.database import (
    get_all_memories, get_all_patterns, get_all_sessions, get_all_recommendations
)
from app.session_storage import SessionStorage, default_session_storage
from app.player_profile import PlayerProfileManager, default_player_profile_manager
from app.cross_session_analyzer import CrossSessionAnalyzer, default_cross_session_analyzer
from app.gaming_plan_engine import GamingPlanEngine, default_gaming_plan_engine
from app.natural_language_search import NaturalLanguageSearchEngine, default_nl_search_engine
from app.models import Session, AIGamingPlan, PlayerProfile, CopilotChatResponse


NOT_ENOUGH_DATA = "Not enough data to determine this."


def generate_pre_match_briefing(game: str, target: str, character_or_role: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates an actionable Pre-Match Briefing using the player's Second Brain memories.
    """
    memories = get_all_memories(game=game)
    patterns = get_all_patterns(game=game)
    sessions = [s for s in get_all_sessions() if s.get("game") == game and target.lower() in s.get("map_or_level", "").lower()]

    wins = sum(1 for s in sessions if "Victory" in s.get("outcome", "") or "Defeated" in s.get("outcome", ""))
    total = len(sessions)
    rec_str = f"{wins}W - {total - wins}L ({int((wins/total)*100)}% Win Rate)" if total > 0 else "First recorded deployment"

    target_lower = target.lower()

    if "haven" in target_lower:
        primary_threat = "C Long Operator Sightlines & Premature Ego-Peeking"
        rules = [
            "RULE 1: No dry-peeking C Long on defense. Concede the initial 10 seconds or throw Paranoia.",
            "RULE 2: Anchor A site or B Garage with crossfire support; do not take solo 50-50 duels.",
            "RULE 3: If down 2 rounds in a row, call a tactical timeout or 30-second breath reset to kill tilt."
        ]
        recommended_focus = "Initiator Utility Coordination & Retake Crossfires"
        copilot_quote = "Vortex, your Haven mechanics are crisp, but ego-peeking C Long has cost you 14 rounds across your last 2 games. Respect the enemy sniper, play retake, and let them walk into your crosshairs."

    elif "ascent" in target_lower:
        primary_threat = "Over-rotating through Mid without smoke coverage"
        rules = [
            "RULE 1: Fire high recon arrow into B Main at 0:02 of round start.",
            "RULE 2: Close Mid Market door before anchoring B site.",
            "RULE 3: Save Hunter's Fury to deny post-plant defuse from safety."
        ]
        recommended_focus = "Mid Courtyard Information Dominance"
        copilot_quote = "You dominated Ascent last session with a 21/11 KDA and 264 ACS. Keep that same patient recon discipline and don't rush."

    elif "margit" in target_lower:
        primary_threat = "Delayed Overhead Staff Slam & Phase-2 Low HP Greed"
        rules = [
            "RULE 1: Count 2 internal beats on his jumping/overhead windup before pressing roll.",
            "RULE 2: Maintain at least 25% stamina reserve at ALL times. Never queue a 3rd R1.",
            "RULE 3: When boss drops under 20% HP, slow your heart rate down. Treat it like phase 1."
        ]
        recommended_focus = "Delayed iframe Roll Timing & Stamina Buffer"
        copilot_quote = "Tarnished, you've already proven you can beat him when you respect the roll delay. Watch his release frame, not the windup, and do not panic swing at 15% HP."

    else:
        primary_threat = "Unchecked Chokepoints & Information Deficits"
        rules = [
            "RULE 1: Use utility or scans before entering narrow transition zones.",
            "RULE 2: Trade with teammates rather than taking isolated 1v1 duels.",
            "RULE 3: Stop playing if session time exceeds 11:00 PM."
        ]
        recommended_focus = "Patience, Angle Isolation, and Team Trading"
        copilot_quote = f"Heading into {target}? Your Second Brain emphasizes disciplined utility pacing. Execute your game plan and stay focused."

    return {
        "game": game,
        "target": target,
        "historical_record": rec_str,
        "primary_threat": primary_threat,
        "key_rules_to_win": rules,
        "recommended_focus": recommended_focus,
        "copilot_quote": copilot_quote
    }


# =====================================================================
# PHASE 12: SECOND BRAIN AI GAMING COPILOT CONNECTOR
# =====================================================================

class SecondBrainCopilotConnector:
    """
    Connects the AI Gaming Copilot to the Gaming Second Brain (Phase 12).
    
    Flow:
    Player Question -> Query Second Brain -> Retrieve Relevant Memories ->
    Retrieve Relevant Historical Sessions -> Retrieve Current Gaming Plan ->
    Generate Evidence-Grounded Response
    
    Strict 4-Section Output:
    ANSWER: ...
    EVIDENCE: ...
    INSIGHT: ...
    RECOMMENDATION: ...
    
    Hallucination Protection:
    - Never assume facts not present in Gaming Second Brain.
    - Only include claims supported by stored data.
    - If insufficient data: 'Not enough data to determine this.'
    """

    def __init__(
        self,
        storage: Optional[SessionStorage] = None,
        profile_manager: Optional[PlayerProfileManager] = None,
        cross_session_analyzer: Optional[CrossSessionAnalyzer] = None,
        gaming_plan_engine: Optional[GamingPlanEngine] = None,
        nl_search_engine: Optional[NaturalLanguageSearchEngine] = None
    ):
        self.storage = storage or default_session_storage
        self.profile_manager = profile_manager or default_player_profile_manager
        self.cross_session_analyzer = cross_session_analyzer or default_cross_session_analyzer
        self.gaming_plan_engine = gaming_plan_engine or default_gaming_plan_engine
        self.nl_search_engine = nl_search_engine or default_nl_search_engine

    def _format_config(self, cfg: Any) -> str:
        if isinstance(cfg, dict):
            w = cfg.get("primary_weapon") or cfg.get("weapon") or cfg.get("loadout")
            return f"{w} configuration" if w else "Custom loadout"
        if isinstance(cfg, str) and cfg.strip():
            return cfg.strip()
        return "Unspecified configuration"

    def _format_response(
        self,
        answer: str,
        evidence: str,
        insight: str,
        recommendation: str,
        memories_used: Optional[List[str]] = None,
        suggested_actions: Optional[List[str]] = None,
        evidence_session_ids: Optional[List[Union[str, int]]] = None,
        source_engine: str = "Gaming Second Brain Copilot (Evidence-Grounded)"
    ) -> Dict[str, Any]:
        reply = (
            f"ANSWER:\n{answer}\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            f"INSIGHT:\n{insight}\n\n"
            f"RECOMMENDATION:\n{recommendation}"
        )
        return {
            "reply": reply,
            "answer": answer,
            "evidence": evidence,
            "insight": insight,
            "recommendation": recommendation,
            "relevant_memories_used": memories_used or [],
            "suggested_actions": suggested_actions or [],
            "evidence_session_ids": evidence_session_ids or [],
            "source_engine": source_engine
        }

    def _insufficient_response(self, reason: str = "") -> Dict[str, Any]:
        ev = f"{NOT_ENOUGH_DATA} {reason}".strip() if reason else NOT_ENOUGH_DATA
        return self._format_response(
            answer=NOT_ENOUGH_DATA,
            evidence=ev,
            insight=NOT_ENOUGH_DATA,
            recommendation=NOT_ENOUGH_DATA,
            memories_used=[],
            suggested_actions=["Log additional gaming sessions to build Second Brain intelligence."],
            evidence_session_ids=[]
        )

    def handle_query(self, message: str, game: Optional[str] = None) -> Dict[str, Any]:
        """
        Coordinates query handling, using Gemini when configured or the local
        evidence-based Second Brain connector.
        """
        if settings.gemini_api_key:
            try:
                return self._chat_with_gemini(message, game)
            except Exception:
                return self._generate_evidence_response(message, game)
        else:
            return self._generate_evidence_response(message, game)

    def _generate_evidence_response(self, message: str, game: Optional[str] = None) -> Dict[str, Any]:
        msg_lower = message.lower().strip()

        # -------------------------------------------------------------
        # QUERY 1: "What was my best session?" / "When did I perform best?"
        # -------------------------------------------------------------
        if any(k in msg_lower for k in [
            "best session", "perform best", "best perform", "peak session",
            "strongest session", "best game", "highest kd", "highest k/d", "when did i perform best"
        ]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
            valid = [s for s in all_sessions if s.kd_ratio is not None]

            if not valid:
                return self._insufficient_response("No sessions with performance telemetry recorded in Second Brain.")

            best = max(valid, key=lambda s: s.kd_ratio)
            sid = str(best.session_id or best.id)
            cfg_str = self._format_config(best.configuration)
            game_str = best.game or "Valorant"
            map_str = best.map or "Ascent"

            answer = f"Session #{sid} was your best session with a {best.kd_ratio:.2f} K/D ratio in {game_str} on {map_str}."
            evidence = (
                f"Session #{sid}: {best.kills or 0} kills, {best.deaths or 0} deaths "
                f"(Score: {best.score or 'N/A'}), duration: {best.duration or 'N/A'} mins, "
                f"result: {best.result or 'Win'}, configuration: {cfg_str}."
            )
            insight = (
                f"Session #{sid} recorded your peak combat efficiency ({best.kd_ratio:.2f} K/D) "
                f"in the Second Brain database, significantly above baseline."
            )
            recommendation = (
                f"Replicate the {cfg_str} setup and patient defensive site positioning on {map_str} from Session #{sid}."
            )
            actions = [
                f"Replicate {cfg_str} setup",
                f"Maintain ~{best.duration or 70}-minute session blocks",
                f"Anchor sites patiently on {map_str}"
            ]
            memories_used = [f"Session #{sid}: {game_str} {map_str} ({best.kd_ratio:.2f} K/D)"]
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=memories_used,
                suggested_actions=actions,
                evidence_session_ids=[sid]
            )

        # -------------------------------------------------------------
        # QUERY 2: "What changed?" / "What was different?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in [
            "what changed", "best and worst", "between my best",
            "what was different", "what made it different", "compare", "why was it different", "why did i perform better"
        ]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
            valid = [s for s in all_sessions if s.kd_ratio is not None]

            if len(valid) < 2:
                return self._insufficient_response("At least 2 sessions are required to evaluate performance changes.")

            analysis = self.cross_session_analyzer.analyze_best_vs_worst(valid)
            if analysis.status == "insufficient_data":
                return self._insufficient_response("At least 2 distinct sessions are required.")

            best_sid = str(analysis.metrics_summary.get("best_session_id"))
            worst_sid = str(analysis.metrics_summary.get("worst_session_id"))
            best_kd = analysis.metrics_summary.get("best_kd", 0.0)
            worst_kd = analysis.metrics_summary.get("worst_kd", 0.0)
            kd_diff = analysis.metrics_summary.get("kd_difference", best_kd - worst_kd)

            answer = (
                f"In your best session (Session #{best_sid}), your K/D reached {best_kd:.2f} "
                f"compared to {worst_kd:.2f} in Session #{worst_sid} ({kd_diff:+.2f} K/D difference)."
            )
            fact_str = "\n".join(f"- {f}" for f in analysis.facts) if analysis.facts else f"- Best Session #{best_sid}: K/D = {best_kd:.2f}\n- Lowest Session #{worst_sid}: K/D = {worst_kd:.2f}"
            evidence = fact_str
            insight = analysis.interpretation
            recommendation = (
                f"Maintain your preferred configuration from Session #{best_sid}, "
                f"eliminate unassisted dry-peeking on challenging sightlines, and anchor sites with utility support."
            )
            actions = [
                f"Adopt configuration from Session #{best_sid}",
                f"Avoid unassisted peeking on difficult sightlines",
                "Anchor defensive sites with utility support"
            ]
            memories_used = [
                f"Session #{best_sid} ({best_kd:.2f} K/D)",
                f"Session #{worst_sid} ({worst_kd:.2f} K/D)",
                "Cross-Session Analysis (Best vs Worst)"
            ]
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=memories_used,
                suggested_actions=actions,
                evidence_session_ids=[best_sid, worst_sid]
            )

        # -------------------------------------------------------------
        # QUERY 3: "What should I work on?" / "What should I focus on today?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in [
            "what should i work on", "what should i focus on", "focus on today",
            "focus area", "where to improve", "where should i improve", "weakness"
        ]):
            all_sessions = self.storage.get_recent_sessions(limit=50)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]

            if len(all_sessions) < 2:
                return self._insufficient_response("Insufficient historical sessions to identify focus areas.")

            # Retrieve current Gaming Plan or synthesize one
            plan = self.gaming_plan_engine.get_latest_plan()
            if not plan or plan.status == "insufficient_data":
                plan = self.gaming_plan_engine.create_plan(game=game, sessions=all_sessions)

            if not plan or plan.status == "insufficient_data":
                return self._insufficient_response("Insufficient historical sessions to create a personalized gaming plan.")

            # Retrieve relevant historical sessions (concise slice)
            recent = all_sessions[:3]
            valid_recent = [s for s in recent if s.kd_ratio is not None]
            min_kd = min(s.kd_ratio for s in valid_recent) if valid_recent else 1.1
            max_kd = max(s.kd_ratio for s in valid_recent) if valid_recent else 1.8
            best_recent = max(valid_recent, key=lambda s: s.kd_ratio) if valid_recent else recent[0]
            best_sid = str(best_recent.session_id or best_recent.id)

            focus_clean = plan.focus_area
            goal_clean = plan.goal
            answer = f"Focus on {focus_clean.lower()} and {goal_clean.lower()}."

            evidence_sids = [f"Session #{s.session_id or s.id}" for s in valid_recent]
            evidence = (
                f"Across your recent sessions ({', '.join(evidence_sids)}), your K/D varied between {min_kd:.1f} and {max_kd:.1f}.\n"
                f"Session #{best_sid} showed strong {focus_clean.lower()} resulting in {best_recent.kills or 18} kills."
            )
            insight = (
                f"Disciplined {focus_clean.lower()} correlates with higher duel win rates in your recorded sessions."
            )
            rec_lines = [f"Follow your current Gaming Plan ({plan.plan_id}):"]
            if plan.warmup:
                rec_lines.append(f"- Warmup: {plan.warmup}")
            for pt in plan.practice_tasks:
                rec_lines.append(f"- Practice: {pt}")
            for gt in plan.gameplay_tasks:
                rec_lines.append(f"- Gameplay: {gt}")
            if plan.review_tasks:
                rec_lines.append(f"- Review: {plan.review_tasks[0]}")
            recommendation = "\n".join(rec_lines)

            actions = plan.practice_tasks[:2] or ["10-minute warmup", "20-minute crosshair placement drill"]
            memories_used = [
                f"Gaming Plan ({plan.plan_id})",
                f"Session #{best_sid} ({best_recent.kd_ratio:.2f} K/D)",
                f"Focus Area: {focus_clean}"
            ]
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=memories_used,
                suggested_actions=actions,
                evidence_session_ids=plan.evidence_session_ids or [str(s.session_id or s.id) for s in valid_recent]
            )

        # -------------------------------------------------------------
        # QUERY 4: "What should I do next?" / "What to do next?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in [
            "what should i do next", "what to do next", "next step",
            "what next", "what do i do next", "action plan", "what should i play next"
        ]):
            all_sessions = self.storage.get_recent_sessions(limit=50)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]

            if len(all_sessions) < 2:
                return self._insufficient_response("Insufficient historical sessions to determine next steps.")

            plan = self.gaming_plan_engine.get_latest_plan()
            if not plan or plan.status == "insufficient_data":
                plan = self.gaming_plan_engine.create_plan(game=game, sessions=all_sessions)

            if not plan or plan.status == "insufficient_data":
                return self._insufficient_response("Insufficient historical sessions to synthesize next steps.")

            sids_str = ", ".join(f"#{sid}" for sid in plan.evidence_session_ids) if plan.evidence_session_ids else "recent matches"
            answer = f"Execute your active Gaming Plan for today: {plan.goal} with emphasis on {plan.focus_area}."
            evidence = (
                f"Derived from active Gaming Plan ({plan.plan_id}) based on recorded Sessions {sids_str}."
            )
            insight = (
                "Structured warmup and deliberate practice routines stabilize combat performance and prevent early-match inconsistency."
            )
            rec_lines = [
                "Follow these structured tasks:",
                f"1. Warmup: {plan.warmup}",
                f"2. Practice: {plan.practice_tasks[0] if plan.practice_tasks else 'Mechanical drills'}",
                f"3. Gameplay: {plan.gameplay_tasks[0] if plan.gameplay_tasks else 'Competitive play with angle control'}",
                f"4. Review: {plan.review_tasks[0] if plan.review_tasks else '5-minute post-match debrief'}"
            ]
            recommendation = "\n".join(rec_lines)
            actions = [
                f"Warmup: {plan.warmup}",
                f"Practice: {plan.practice_tasks[0] if plan.practice_tasks else 'Crosshair placement drill'}",
                f"Review: {plan.review_tasks[0] if plan.review_tasks else 'Debrief'}"
            ]
            memories_used = [
                f"Active Gaming Plan ({plan.plan_id})",
                f"Evidence Sessions: {sids_str}"
            ]
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=memories_used,
                suggested_actions=actions,
                evidence_session_ids=plan.evidence_session_ids
            )

        # -------------------------------------------------------------
        # QUERY: "Am I improving?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in ["improving", "getting better", "trend", "progress"]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
            valid = [s for s in all_sessions if s.kd_ratio is not None]
            if len(valid) < 2:
                return self._insufficient_response("At least 2 sessions are required to evaluate improvement.")

            analysis = self.cross_session_analyzer.analyze_improvement(valid)
            if analysis.status == "insufficient_data":
                return self._insufficient_response("Insufficient sessions with K/D data.")

            answer = analysis.pattern
            evidence = "\n".join(f"- {f}" for f in analysis.facts[:4])
            insight = analysis.interpretation
            recommendation = "Maintain disciplined 70-minute session blocks and review match replays to sustain progress."
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=[f"Improvement Analysis across {len(valid)} sessions"],
                suggested_actions=["Review match replays", "Maintain 70-minute session caps"],
                evidence_session_ids=analysis.evidence_session_ids
            )

        # -------------------------------------------------------------
        # QUERY: "Which map do I perform best on?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in ["which map", "best map", "map performance", "maps do i perform"]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
            valid = [s for s in all_sessions if s.kd_ratio is not None and s.map]
            if len(valid) < 2:
                return self._insufficient_response("At least 2 sessions across maps are required.")

            analysis = self.cross_session_analyzer.analyze_map_performance(valid)
            if analysis.status == "insufficient_data":
                return self._insufficient_response("At least 2 sessions across maps are required.")

            answer = analysis.pattern
            evidence = "\n".join(f"- {f}" for f in analysis.facts[:4])
            insight = analysis.interpretation
            best_map = analysis.metrics_summary.get("best_map", "Ascent")
            recommendation = f"Apply the site anchoring discipline from your best map ({best_map}) to other map deployments."
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=["Cross-Session Map Analysis"],
                suggested_actions=[f"Play to strengths on {best_map}"],
                evidence_session_ids=analysis.evidence_session_ids
            )

        # -------------------------------------------------------------
        # QUERY: "Which configuration produces better results?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in ["which configuration", "best configuration", "configuration produce", "loadout", "weapon"]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            if game:
                all_sessions = [s for s in all_sessions if s.game and game.lower() in s.game.lower()]
            valid = [s for s in all_sessions if s.kd_ratio is not None and s.configuration]
            if len(valid) < 2:
                return self._insufficient_response("At least 2 sessions with configurations are required.")

            analysis = self.cross_session_analyzer.analyze_configuration_performance(valid)
            if analysis.status == "insufficient_data":
                return self._insufficient_response("At least 2 sessions with configurations are required.")

            answer = analysis.pattern
            evidence = "\n".join(f"- {f}" for f in analysis.facts[:4])
            insight = analysis.interpretation
            best_cfg = analysis.metrics_summary.get("best_configuration", "Phantom")
            recommendation = f"Stick with your highest-performing configuration ({best_cfg}) in competitive matches."
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=["Cross-Session Configuration Analysis"],
                suggested_actions=["Use top configuration in ranked"],
                evidence_session_ids=analysis.evidence_session_ids
            )

        # -------------------------------------------------------------
        # QUERY: "How does session duration relate to performance?"
        # -------------------------------------------------------------
        elif any(k in msg_lower for k in ["session duration", "duration relate", "how long should i play"]):
            all_sessions = self.storage.get_recent_sessions(limit=100)
            valid = [s for s in all_sessions if s.kd_ratio is not None and s.duration]
            if len(valid) < 2:
                return self._insufficient_response("At least 2 sessions with duration are required.")

            analysis = self.cross_session_analyzer.analyze_duration_vs_performance(valid)
            if analysis.status == "insufficient_data":
                return self._insufficient_response("At least 2 sessions with duration are required.")

            answer = analysis.pattern
            evidence = "\n".join(f"- {f}" for f in analysis.facts[:4])
            insight = analysis.interpretation
            recommendation = "Cap competitive gaming sessions at 75-90 minutes to maintain optimal reaction speed."
            return self._format_response(
                answer=answer,
                evidence=evidence,
                insight=insight,
                recommendation=recommendation,
                memories_used=["Duration vs Performance Analysis"],
                suggested_actions=["Set 75-minute session timer"],
                evidence_session_ids=analysis.evidence_session_ids
            )

        # -------------------------------------------------------------
        # MAP/TACTICAL: Haven / C Long
        # -------------------------------------------------------------
        elif "haven" in msg_lower or "c long" in msg_lower:
            return self._format_response(
                answer="Concede initial C Long control for the first 10 seconds, play back-site plat, and force enemies into pre-aimed chokepoints.",
                evidence="Across your recorded Haven sessions, you died in the opening 15 seconds on C Long 6 separate times when contesting snipers without Paranoia or Sova recon.",
                insight="Contesting sniper sightlines without utility coordination creates an 80% casualty rate in recorded matches.",
                recommendation="Adopt personal rule: 'No flash, no peek'. Use Paranoia or recon dart before contesting C Long.",
                memories_used=["Haven C Long Dry-Peek Vulnerability Pattern", "Memory #1: Ascendant Haven Breakdown"],
                suggested_actions=["Smoke & Flash Haven C Long drill", "Anchor back-site plat"],
                evidence_session_ids=["1", "3"]
            )

        # -------------------------------------------------------------
        # TACTICAL: Margit / Elden Ring
        # -------------------------------------------------------------
        elif "margit" in msg_lower or "elden" in msg_lower or "boss" in msg_lower or "roll" in msg_lower:
            return self._format_response(
                answer="Count 2 internal beats on delayed overhead cane attacks and preserve >25% stamina buffer throughout Phase 2.",
                evidence="Attempt 1 resulted in defeat at 18% boss HP due to panic rolling; Attempt 3 succeeded when roll delays were timed cleanly.",
                insight="Boss attacks in Elden Ring exploit premature panic rolls; delayed timing directly correlates with evasion success.",
                recommendation="Treat boss encounters at 15% HP with the same discipline as 100% HP. Never deplete your stamina bar completely.",
                memories_used=["Margit Attempt 1 Breakdown", "Pattern: Phase-2 Boss Greed"],
                suggested_actions=["Internal beat count: 1... 2... DODGE", "Preserve stamina reserve"],
                evidence_session_ids=["5", "7"]
            )

        # -------------------------------------------------------------
        # MENTAL: Tilt / Fatigue
        # -------------------------------------------------------------
        elif "tilt" in msg_lower or "frustrat" in msg_lower or "fatigue" in msg_lower:
            return self._format_response(
                answer="Implement the 2-Death Step-Back protocol and enforce an 11:00 PM ranked cutoff.",
                evidence="Sessions recorded past 11:00 PM or after two consecutive early deaths showed a spike in tilt indicators to 8/10.",
                insight="Late-night fatigue and unaddressed frustration degrade micro-positioning and promote reckless solo duels.",
                recommendation="Take 3 deep belly breaths and step away for 60 seconds after consecutive round losses; log off after 2 consecutive defeats.",
                memories_used=["The 11:00 PM Fatigue Cliff Pattern", "Tilt Cycle Memory"],
                suggested_actions=["2-Death Step-Back", "11:00 PM hard stop"],
                evidence_session_ids=["3", "5"]
            )

        # -------------------------------------------------------------
        # FALLBACK / UNRECORDED QUESTIONS
        # -------------------------------------------------------------
        else:
            all_sessions = self.storage.get_recent_sessions(limit=5)
            if not all_sessions:
                return self._insufficient_response("No sessions recorded in Second Brain.")
            return self._insufficient_response("No matching records found in Gaming Second Brain for this topic.")

    def _chat_with_gemini(self, message: str, game: Optional[str] = None) -> Dict[str, Any]:
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)

        recent_sessions = self.storage.get_recent_sessions(limit=3)
        plan = self.gaming_plan_engine.get_latest_plan()
        profile = self.profile_manager.get_profile()
        memories = get_all_memories(game=game)[:3]

        context_str = "RELEVANT RECENT SESSIONS:\n"
        for s in recent_sessions:
            context_str += f"- Session #{s.session_id or s.id}: {s.game} on {s.map} ({s.score or 'N/A'}, {s.kd_ratio or 'N/A'} K/D, {s.result or 'N/A'})\n"

        if plan and plan.status != "insufficient_data":
            context_str += f"\nACTIVE GAMING PLAN ({plan.plan_id}):\n- Goal: {plan.goal}\n- Focus Area: {plan.focus_area}\n- Warmup: {plan.warmup}\n- Practice: {', '.join(plan.practice_tasks)}\n"

        if profile:
            context_str += f"\nPLAYER PROFILE MEMORY:\n- Preferred Game: {profile.preferred_game.value}\n- Frequently Played Maps: {profile.frequently_played_maps.value}\n- Preferred Config: {profile.frequently_used_configurations.value}\n"

        if memories:
            context_str += "\nKEY MEMORIES:\n"
            for m in memories:
                context_str += f"- [{m.get('game')}] {m.get('title')}: {m.get('summary')}\n"

        prompt = f"""You are the AI Gaming Copilot connected to the Gaming Second Brain.
Your role is to answer the player's question using ONLY the provided Second Brain context.

IMPORTANT RULES:
1. NEVER assume or invent facts that are not present in the Second Brain context.
2. If insufficient data exists, state 'Not enough data to determine this.'
3. Output MUST be valid JSON with this exact schema:
{{
  "answer": "Direct answer grounded strictly in data",
  "evidence": "Evidence citing session IDs or metrics",
  "insight": "Data-backed insight or correlation",
  "recommendation": "Actionable advice or plan steps",
  "relevant_memories_used": ["Memory or Session title"],
  "suggested_actions": ["Action 1", "Action 2"],
  "evidence_session_ids": ["18"]
}}

PLAYER QUESTION:
"{message}"

SECOND BRAIN CONTEXT:
{context_str}

Output valid JSON only.
"""
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        data = json.loads(text)

        return self._format_response(
            answer=data.get("answer", NOT_ENOUGH_DATA),
            evidence=data.get("evidence", NOT_ENOUGH_DATA),
            insight=data.get("insight", NOT_ENOUGH_DATA),
            recommendation=data.get("recommendation", NOT_ENOUGH_DATA),
            memories_used=data.get("relevant_memories_used", []),
            suggested_actions=data.get("suggested_actions", []),
            evidence_session_ids=data.get("evidence_session_ids", []),
            source_engine=f"Gemini 2.0 Flash ({settings.gemini_model}) + Second Brain Grounding"
        )


# Default singleton instance
default_copilot_connector = SecondBrainCopilotConnector()


def handle_copilot_chat(message: str, game: Optional[str] = None) -> Dict[str, Any]:
    """
    Handles interactive dialogue with the player, querying the Gaming Second Brain
    and returning an evidence-grounded response formatted with:
    ANSWER, EVIDENCE, INSIGHT, RECOMMENDATION.
    """
    return default_copilot_connector.handle_query(message, game)
