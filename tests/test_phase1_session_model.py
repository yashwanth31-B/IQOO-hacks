import os
import sys
import unittest
from datetime import datetime
from pydantic import ValidationError

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Session

class TestPhase1SessionDataModel(unittest.TestCase):
    """
    Phase 1: Session Data Model Tests
    Validates all rules and test cases required by the Phase 1 specification:
    1. Complete session.
    2. Partial session.
    3. Deaths = 0.
    4. Negative kills.
    5. Negative duration.
    6. Different game.
    7. Custom performance metrics.
    """

    # -------------------------------------------------------------
    # TEST 1: Complete Session
    # -------------------------------------------------------------
    def test_1_complete_session(self):
        """
        Test 1: Complete session with all fields populated across:
        Identity, Game, Timing, Performance, Outcome, Player, Data Quality, AI.
        """
        payload = {
            # Identity
            "session_id": "session-val-018",
            # Game
            "game": "Valorant",
            "game_mode": "Competitive",
            "map": "Ascent",
            "configuration": {
                "primary_weapon": "Phantom",
                "secondary_weapon": "Ghost",
                "sensitivity": 0.35,
                "dpi": 800,
                "crosshair_code": "0;P;c;5;o;1;d;1;z;3"
            },
            # Timing
            "started_at": "2026-09-18T14:00:00",
            "ended_at": "2026-09-18T15:12:00",
            "duration": 72,
            # Performance
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "assists": 6,
            "performance_metrics": {
                "acs": 285,
                "headshot_pct": 32.5,
                "first_bloods": 5,
                "clutches_won": 2,
                "damage_dealt": 2840
            },
            # Outcome
            "result": "Win",
            # Player
            "player_notes": "Crosshair placement was locked in. Sensitivity tweak was perfect.",
            "tags": ["#Ranked", "#Ascent", "#Phantom", "#MVP"],
            # Data Quality
            "data_source": "riot_api_client",
            "data_completeness": 1.0,
            # AI (initially null)
            "ai_summary": None,
            "ai_insights": None
        }

        session = Session(**payload)

        # Identity
        self.assertEqual(session.session_id, "session-val-018")

        # Game
        self.assertEqual(session.game, "Valorant")
        self.assertEqual(session.game_mode, "Competitive")
        self.assertEqual(session.map, "Ascent")
        self.assertIsInstance(session.configuration, dict)
        self.assertEqual(session.configuration["primary_weapon"], "Phantom")
        self.assertEqual(session.configuration["sensitivity"], 0.35)

        # Timing
        self.assertEqual(session.started_at, "2026-09-18T14:00:00")
        self.assertEqual(session.ended_at, "2026-09-18T15:12:00")
        self.assertEqual(session.duration, 72)

        # Performance & Auto K/D
        self.assertEqual(session.score, "18/10")
        self.assertEqual(session.kills, 18)
        self.assertEqual(session.deaths, 10)
        self.assertEqual(session.assists, 6)
        self.assertEqual(session.kd_ratio, 1.8)  # 18 / 10 = 1.8 automatically calculated!
        self.assertEqual(session.performance_metrics["acs"], 285)

        # Outcome
        self.assertEqual(session.result, "Win")

        # Player
        self.assertEqual(session.player_notes, "Crosshair placement was locked in. Sensitivity tweak was perfect.")
        self.assertEqual(len(session.tags), 4)

        # Data Quality
        self.assertEqual(session.data_source, "riot_api_client")
        self.assertEqual(session.data_completeness, 1.0)

        # AI (initially null)
        self.assertIsNone(session.ai_summary)
        self.assertIsNone(session.ai_insights)

    # -------------------------------------------------------------
    # TEST 2: Partial Session
    # -------------------------------------------------------------
    def test_2_partial_session(self):
        """
        Test 2: Partial session with minimal fields.
        Must work when most data is missing, and MUST NOT invent missing data.
        """
        # A completely empty session must be valid
        empty_session = Session()
        self.assertIsNone(empty_session.session_id)
        self.assertIsNone(empty_session.game)
        self.assertIsNone(empty_session.kills)
        self.assertIsNone(empty_session.deaths)
        self.assertIsNone(empty_session.kd_ratio)
        self.assertIsNone(empty_session.duration)
        self.assertIsNone(empty_session.score)
        self.assertIsNone(empty_session.result)
        self.assertIsNone(empty_session.ai_summary)
        self.assertIsNone(empty_session.ai_insights)
        self.assertEqual(empty_session.performance_metrics, {})
        self.assertEqual(empty_session.tags, [])

        # Partial session with only 2 fields
        partial = Session(
            game="Overwatch 2",
            result="Victory"
        )
        self.assertEqual(partial.game, "Overwatch 2")
        self.assertEqual(partial.result, "Victory")
        # Do not invent missing data
        self.assertIsNone(partial.duration)
        self.assertIsNone(partial.kills)
        self.assertIsNone(partial.deaths)
        self.assertIsNone(partial.kd_ratio)
        self.assertIsNone(partial.score)
        self.assertIsNone(partial.map)
        self.assertIsNone(partial.configuration)
        # Completeness accurately computed based on actual non-empty core fields
        self.assertGreater(partial.data_completeness, 0.0)
        self.assertLess(partial.data_completeness, 1.0)

    # -------------------------------------------------------------
    # TEST 3: Deaths = 0
    # -------------------------------------------------------------
    def test_3_deaths_equal_zero(self):
        """
        Test 3: Handle deaths = 0 safely.
        Must not raise ZeroDivisionError.
        """
        # Case A: Kills > 0, Deaths = 0 (Flawless match)
        session_flawless = Session(
            kills=15,
            deaths=0
        )
        self.assertEqual(session_flawless.kills, 15)
        self.assertEqual(session_flawless.deaths, 0)
        self.assertEqual(session_flawless.kd_ratio, 15.0)

        # Case B: Kills = 0, Deaths = 0 (Peaceful / no engagements)
        session_zero = Session(
            kills=0,
            deaths=0
        )
        self.assertEqual(session_zero.kd_ratio, 0.0)

    # -------------------------------------------------------------
    # TEST 4: Negative Kills (Reject)
    # -------------------------------------------------------------
    def test_4_negative_kills_rejection(self):
        """
        Test 4: Reject negative kills.
        Must raise ValidationError / ValueError.
        """
        with self.assertRaises(ValidationError) as ctx:
            Session(kills=-1)
        self.assertIn("cannot be negative", str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            Session(kills=-25)
        self.assertIn("cannot be negative", str(ctx.exception))

        # Also verify rejection of negative deaths and negative assists
        with self.assertRaises(ValidationError) as ctx:
            Session(deaths=-2)
        self.assertIn("cannot be negative", str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            Session(assists=-4)
        self.assertIn("cannot be negative", str(ctx.exception))

    # -------------------------------------------------------------
    # TEST 5: Negative Duration (Reject)
    # -------------------------------------------------------------
    def test_5_negative_duration_rejection(self):
        """
        Test 5: Reject negative duration.
        Must raise ValidationError / ValueError for numeric and string inputs.
        """
        # Numeric negative duration
        with self.assertRaises(ValidationError) as ctx:
            Session(duration=-30)
        self.assertIn("duration cannot be negative", str(ctx.exception))

        # String negative duration
        with self.assertRaises(ValidationError) as ctx:
            Session(duration="-15 minutes")
        self.assertIn("duration cannot be negative", str(ctx.exception))

        # Float negative duration
        with self.assertRaises(ValidationError) as ctx:
            Session(duration=-1.5)
        self.assertIn("duration cannot be negative", str(ctx.exception))

    # -------------------------------------------------------------
    # TEST 6: Different Game (Game-Agnostic Core Model)
    # -------------------------------------------------------------
    def test_6_different_games(self):
        """
        Test 6: Test that the model works for completely different games
        without any hard-coded Valorant-specific fields or restrictions.
        """
        # Game A: Elden Ring (Action RPG / Boss Progression)
        elden_ring_session = Session(
            session_id="er-malenia-attempt-03",
            game="Elden Ring",
            game_mode="Boss Fight",
            map="Elphael, Brace of the Haligtree",
            configuration={
                "build": "Dexterity / Bleed",
                "right_hand": "Rivers of Blood +10",
                "talismans": ["Lord of Blood's Exultation", "Dragoncrest Greatshield", "Rotten Winged Sword"],
                "rune_level": 140
            },
            duration=8,
            result="Defeat (Phase 2 - 20% HP)",
            kills=0,
            deaths=1,
            player_notes="Greeded R1 during Scarlet Aeonia recovery instead of waiting for petal clear."
        )
        self.assertEqual(elden_ring_session.game, "Elden Ring")
        self.assertEqual(elden_ring_session.map, "Elphael, Brace of the Haligtree")
        self.assertEqual(elden_ring_session.kd_ratio, 0.0)
        self.assertEqual(elden_ring_session.configuration["rune_level"], 140)

        # Game B: Apex Legends (Battle Royale)
        apex_session = Session(
            session_id="apex-ranked-s20",
            game="Apex Legends",
            game_mode="Ranked Battle Royale",
            map="Storm Point",
            configuration="Bangalore (R-301 + Mastiff)",
            duration="22 minutes",
            score="1st Place (Champion)",
            kills=7,
            deaths=1,
            assists=4,
            result="Victory",
            tags=["#Champion", "#StormPoint"]
        )
        self.assertEqual(apex_session.game, "Apex Legends")
        self.assertEqual(apex_session.kd_ratio, 7.0)
        self.assertEqual(apex_session.result, "Victory")

        # Game C: Counter-Strike 2
        cs2_session = Session(
            game="Counter-Strike 2",
            game_mode="Premier",
            map="Mirage",
            configuration="M4A1-S + Desert Eagle",
            duration=42,
            score="13-9",
            kills=24,
            deaths=14,
            assists=5,
            result="Win"
        )
        self.assertEqual(cs2_session.game, "Counter-Strike 2")
        self.assertEqual(cs2_session.kd_ratio, 1.71)  # 24 / 14 = 1.714... rounded to 1.71

    # -------------------------------------------------------------
    # TEST 7: Custom Performance Metrics (Extensible Telemetry)
    # -------------------------------------------------------------
    def test_7_custom_performance_metrics(self):
        """
        Test 7: Extensible performance_metrics dictionary holding arbitrary
        game-specific data structures and statistics.
        """
        # Fighting Game custom metrics
        fg_metrics = {
            "drive_rush_cancels": 12,
            "punish_counter_combos": 7,
            "perfect_parries": 4,
            "corner_carry_pct": 68.2,
            "super_art_hits": {
                "sa1": 2,
                "sa2": 0,
                "sa3_ca": 1
            }
        }
        fg_session = Session(
            game="Street Fighter 6",
            game_mode="Ranked Matches",
            configuration="Luke (Classic Controls)",
            performance_metrics=fg_metrics,
            result="Win (2-1 Sets)"
        )
        self.assertDictEqual(fg_session.performance_metrics, fg_metrics)
        self.assertEqual(fg_session.performance_metrics["perfect_parries"], 4)
        self.assertEqual(fg_session.performance_metrics["super_art_hits"]["sa3_ca"], 1)

        # Rocket League custom metrics
        rl_metrics = {
            "goals": 4,
            "saves": 3,
            "shots": 8,
            "boost_collected_big": 14,
            "aerial_touches": 18,
            "overtime": True
        }
        rl_session = Session(
            game="Rocket League",
            game_mode="2v2 Competitive",
            configuration="Octane (Standard Boost)",
            performance_metrics=rl_metrics,
            score="4-3 OT",
            result="Win"
        )
        self.assertEqual(rl_session.performance_metrics["goals"], 4)
        self.assertTrue(rl_session.performance_metrics["overtime"])

    def test_ai_metadata_fields_and_raw_separation(self):
        """
        Verify that match_id and all AI metadata fields are properly supported,
        and that raw player data is kept strictly distinct from AI metadata.
        """
        s = Session(
            session_id="session-meta-001",
            match_id="match-riot-na-98765",
            game="Valorant",
            game_mode="Competitive",
            map="Ascent",
            started_at="2026-09-18T19:00:00",
            ended_at="2026-09-18T19:45:00",
            duration=45,
            score="13-8",
            kills=20,
            deaths=10,
            assists=5,
            result="Win",
            configuration={"primary_weapon": "Phantom"},
            performance_metrics={"acs": 290, "headshot_pct": 28.0},
            player_notes="Clean site holds.",
            tags=["competitive", "ascent"],
            data_source="client_api",
            data_completeness=1.0,
            # AI Metadata
            ai_summary="Dominant competitive win on Ascent with 2.0 K/D.",
            ai_insights=["High combat conversion using Phantom."],
            memory_text="Session #session-meta-001: 20 kills, 10 deaths on Ascent.",
            memory_importance=8.5,
            ai_confidence=0.95,
            evidence_session_ids=["session-meta-001"],
            ai_model_version="gaming-second-brain-ai-v1",
            processing_status="processed"
        )

        # Raw player fields
        self.assertEqual(s.match_id, "match-riot-na-98765")
        self.assertEqual(s.kd_ratio, 2.0)
        self.assertEqual(s.kills, 20)
        self.assertEqual(s.player_notes, "Clean site holds.")

        # AI metadata fields
        self.assertEqual(s.ai_summary, "Dominant competitive win on Ascent with 2.0 K/D.")
        self.assertEqual(s.memory_text, "Session #session-meta-001: 20 kills, 10 deaths on Ascent.")
        self.assertEqual(s.memory_importance, 8.5)
        self.assertEqual(s.ai_confidence, 0.95)
        self.assertEqual(s.evidence_session_ids, ["session-meta-001"])
        self.assertEqual(s.ai_model_version, "gaming-second-brain-ai-v1")
        self.assertEqual(s.processing_status, "processed")

    def test_incomplete_sessions_never_invent_fields(self):
        """
        Verify that in an incomplete session, missing fields remain None / empty
        and are never fabricated or guessed.
        """
        sparse = Session(
            game="Apex Legends",
            kills=5
        )
        # Present fields
        self.assertEqual(sparse.game, "Apex Legends")
        self.assertEqual(sparse.kills, 5)

        # Never invent missing fields
        self.assertIsNone(sparse.deaths)
        self.assertIsNone(sparse.kd_ratio)
        self.assertIsNone(sparse.assists)
        self.assertIsNone(sparse.score)
        self.assertIsNone(sparse.map)
        self.assertIsNone(sparse.match_id)
        self.assertIsNone(sparse.duration)
        self.assertIsNone(sparse.result)
        self.assertIsNone(sparse.configuration)
        self.assertIsNone(sparse.player_notes)
        self.assertIsNone(sparse.ai_summary)
        self.assertIsNone(sparse.ai_insights)
        self.assertIsNone(sparse.memory_text)
        self.assertIsNone(sparse.memory_importance)
        self.assertIsNone(sparse.ai_confidence)
        self.assertEqual(sparse.evidence_session_ids, [])
        self.assertIsNone(sparse.ai_model_version)
        self.assertEqual(sparse.processing_status, "pending")


if __name__ == "__main__":
    unittest.main()

