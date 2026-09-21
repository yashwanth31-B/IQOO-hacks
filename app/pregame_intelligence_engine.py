"""
Gaming Second Brain — Pre-Game Intelligence Engine
Orchestrates the entire Pre-Game Intelligence System in sub-3-second latency:

GAME OPENED
    ↓
IDENTIFY PLAYER EXPERIENCE
    ↓
DETECT GAME
    ↓
DETECT MAP
    ↓
LOAD MAP INTELLIGENCE
    ↓
LOAD PLAYER HISTORY
    ↓
GENERATE 3-SECOND PRE-GAME PLAN
    ↓
SHOW STRATEGY + MAP AREAS + LOADOUT INFORMATION
    ↓
START SESSION
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.models import (
    PlayerExperienceProfile,
    GameDetectionResult,
    MapDetectionResult,
    MapAreaIntelligence,
    WeaponRecommendation,
    MapLoadoutStrategy,
    RotationIntelligence,
    PreGameAdaptivePlan,
    PreGameIntelligenceResponse,
    PreGameIntelligenceRequest,
    Session
)
from app.detection import GameMapDetector, default_detector
from app.player_experience import PlayerExperienceDetector, default_player_experience_detector
from app.map_intelligence import MapIntelligenceModule, default_map_intelligence_module
from app.weapon_intelligence import WeaponIntelligenceModule, default_weapon_intelligence_module
from app.session_storage import SessionStorage, default_session_storage


class PreGameIntelligenceEngine:
    """
    Sub-3-second Pre-Game Intelligence Orchestrator.
    Combines cached profiles, verified map data, weapon performance,
    and adaptive strategy generation without hallucinations.
    """

    def __init__(
        self,
        detector: Optional[GameMapDetector] = None,
        experience_detector: Optional[PlayerExperienceDetector] = None,
        map_module: Optional[MapIntelligenceModule] = None,
        weapon_module: Optional[WeaponIntelligenceModule] = None,
        storage: Optional[SessionStorage] = None
    ):
        self.detector = detector or default_detector
        self.experience_detector = experience_detector or default_player_experience_detector
        self.map_module = map_module or default_map_intelligence_module
        self.weapon_module = weapon_module or default_weapon_intelligence_module
        self.storage = storage or default_session_storage

    def run_pregame_intelligence(
        self,
        game: str,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        detection_source: str = "simulated",
        player_name: str = "Manoj",
        include_ai: bool = True,
        simulate_timeout: bool = False,
        simulate_failure: bool = False
    ) -> PreGameIntelligenceResponse:
        """
        Executes the full Pre-Game Intelligence pipeline in < 3 seconds.
        """
        t0 = time.perf_counter()

        # Step 1: Detect Game
        game_result = self.detector.detect_game(
            source=detection_source,
            game_hint=game,
            mode_hint=game_mode
        )
        resolved_game = game_result.game or game or "Unknown Game"

        # Step 2: Detect Map
        map_result = self.detector.detect_map(
            game=resolved_game,
            source=detection_source,
            map_hint=map_name
        )
        resolved_map = map_result.map

        # Step 3: Identify Player Experience from Stored History
        experience_profile = self.experience_detector.get_experience_profile(
            game=resolved_game,
            player_name=player_name
        )

        # Step 4: Load Map Intelligence (Verified Map Areas)
        map_areas = self.map_module.get_map_areas(resolved_game, resolved_map)
        low_enemy_areas, _ = self.map_module.get_low_enemy_areas(resolved_game, resolved_map)
        high_activity_areas, _ = self.map_module.get_high_activity_areas(resolved_game, resolved_map)

        # Step 5: Recommended Drop / Start Area
        recommended_start = self.map_module.recommend_start_area(
            game=resolved_game,
            map_name=resolved_map,
            experience_profile=experience_profile
        )

        # Avoid / High Activity Areas list
        avoid_areas = [a.area_name for a in high_activity_areas]

        # Step 6: Weapon Intelligence & Loadout Recommendation
        weapon_rec = self.weapon_module.calculate_best_loadout(
            game=resolved_game,
            map_name=resolved_map
        )

        # Step 7: Map Loadout Strategy
        start_area_name = recommended_start["area"] if recommended_start else None
        map_loadout_strategy = self.map_module.get_map_loadout_strategy(
            game=resolved_game,
            map_name=resolved_map,
            starting_area_name=start_area_name
        )

        # Step 8: Rotation Intelligence
        rotation_plan = self.map_module.get_rotation_plan(
            game=resolved_game,
            map_name=resolved_map,
            starting_area_name=start_area_name
        )

        # Step 9: Synthesize Player-Adaptive Map Plan
        adaptive_plan = self._generate_adaptive_plan(
            game=resolved_game,
            map_name=resolved_map,
            experience_profile=experience_profile,
            recommended_start=recommended_start,
            avoid_areas=avoid_areas,
            weapon_rec=weapon_rec,
            simulate_timeout=simulate_timeout,
            simulate_failure=simulate_failure
        )

        # Data sources dictionary for complete audit trail
        data_sources = {
            "player_experience": experience_profile.data_source,
            "game_detection": game_result.detection_source.upper(),
            "map_detection": map_result.detection_source.upper(),
            "map_areas": "HISTORICAL GAME DATA" if map_areas else "NO DATA",
            "enemy_activity": "HISTORICAL GAME DATA" if map_areas else "NO DATA",
            "recommended_start": recommended_start.get("data_source", "GAME DATA") if recommended_start else "NO DATA",
            "weapon_recommendation": weapon_rec.data_source if weapon_rec else "NO DATA",
            "rotation_plan": rotation_plan.data_source if rotation_plan else "NO DATA",
            "strategy": adaptive_plan.data_source if adaptive_plan else "NO DATA"
        }

        # Player greeting header
        greeting = f"Welcome back, {player_name}" if experience_profile.experience_level != "NEW PLAYER" else f"Welcome, {player_name}"

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return PreGameIntelligenceResponse(
            player_experience=experience_profile,
            game_detection=game_result,
            map_detection=map_result,
            map_areas=map_areas,
            low_enemy_areas=low_enemy_areas,
            high_activity_areas=high_activity_areas,
            recommended_start=recommended_start,
            avoid_areas=avoid_areas,
            weapon_recommendation=weapon_rec,
            map_loadout_strategy=map_loadout_strategy,
            rotation_plan=rotation_plan,
            adaptive_plan=adaptive_plan,
            data_sources=data_sources,
            generation_time_ms=elapsed_ms,
            status="PRE-GAME INTELLIGENCE READY",
            player_greeting=greeting,
            created_at=datetime.now().isoformat()
        )

    def _generate_adaptive_plan(
        self,
        game: str,
        map_name: Optional[str],
        experience_profile: PlayerExperienceProfile,
        recommended_start: Optional[Dict[str, Any]],
        avoid_areas: List[str],
        weapon_rec: Optional[WeaponRecommendation],
        simulate_timeout: bool = False,
        simulate_failure: bool = False
    ) -> PreGameAdaptivePlan:
        """
        Requirement 8: Player-Adaptive Map Plan.
        Different plans generated depending on stored player history.
        Handles AI timeout and failure gracefully.
        """
        if simulate_failure:
            # Fallback to deterministic factual plan
            return PreGameAdaptivePlan(
                plan_type="GENERAL PLAN",
                focus="Basic Map Awareness & Positioning",
                start_area=recommended_start["area"] if recommended_start else "Designated Staging Sector",
                priority="Secure Loadout → Establish Cover → Navigate Safe Boundary",
                avoid="Historically high-activity areas",
                review="Post-match engagement review",
                strategy_steps=[
                    "Prioritize covered routes and maintain situational awareness.",
                    "Secure primary loadout before engaging distant targets.",
                    "Rotate before high-risk zones collapse."
                ],
                data_source="HISTORICAL GAME DATA"
            )

        if simulate_timeout:
            # Timeout fallback: return already available factual information first
            return PreGameAdaptivePlan(
                plan_type="FAST FALLBACK PLAN",
                focus="Safe Route Transition",
                start_area=recommended_start["area"] if recommended_start else "Designated Staging Sector",
                priority="Loot → Cover → Safe Rotation",
                avoid="Unverified open crossings",
                review="Engagement notes",
                strategy_steps=[
                    "Prioritize covered routes based on verified map terrain.",
                    "Secure useful loot before initiating long-range engagements.",
                    "Rotate before zone compression."
                ],
                data_source="HISTORICAL GAME DATA"
            )

        exp_level = experience_profile.experience_level.upper()
        start_area = recommended_start["area"] if recommended_start else "Selected Start Area"
        avoid_str = ", ".join(avoid_areas[:2]) if avoid_areas else "Historically high-activity areas until comfortable"

        if "NEW" in exp_level:
            return PreGameAdaptivePlan(
                plan_type="BEGINNER PLAN",
                focus="Survival + map awareness",
                start_area=start_area,
                priority="Loot → Cover → Safe rotation",
                avoid="High-risk areas until comfortable",
                review="Initial game mechanics and map navigation",
                strategy_steps=[
                    f"Start in {start_area} for historically lower enemy activity.",
                    "Secure primary weapon and medical supplies before moving out.",
                    "Avoid early contested hotspots until familiar with weapon recoil."
                ],
                data_source="AI ANALYSIS"
            )

        elif "RETURNING" in exp_level:
            return PreGameAdaptivePlan(
                plan_type="RETURNING PLAYER PLAN",
                focus="Improve previous weakness",
                start_area=start_area,
                priority="Loot → Positioning → Rotation",
                review="Previous session mistakes",
                strategy_steps=[
                    f"Drop in {start_area} for balanced loot and steady positioning.",
                    "Prioritize covered routes and avoid repeated open-field rotations.",
                    "Review previous session positioning deaths after this match."
                ],
                data_source="AI ANALYSIS"
            )

        else:
            # EXPERIENCED PLAYER
            return PreGameAdaptivePlan(
                plan_type="EXPERIENCED PLAYER PLAN",
                focus="Performance optimization",
                start_area=start_area,
                priority="Fast loot → Early rotation → Combat efficiency",
                review="Decision quality + combat performance",
                strategy_steps=[
                    f"Contest {start_area} for immediate high-tier loot and map control.",
                    "Rotate early to secure high-ground vantage before opponent arrival.",
                    "Maintain aggressive crossfire discipline and evaluate duel conversion."
                ],
                data_source="AI ANALYSIS"
            )


# Default singleton instance
default_pregame_intelligence_engine = PreGameIntelligenceEngine()
