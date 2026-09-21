"""
Phase 13: Final Hackathon-Ready Dashboard Test Suite.

Verifies all requirements from Phase 13:
1. Complete dashboard flow end-to-end:
   Open Dashboard -> Detect Game -> Detect Map -> Confirm -> Generate AI Plan
   -> Plan appears in <= 3 seconds -> Start Session -> Show Live Performance
   -> End Session -> Store Session -> Update Memory -> Show Analysis -> Create Next Plan
2. Test Cases specified in prompt:
   - BGMI + Erangel
   - Valorant + Ascent
   - Incomplete historical data
   - No historical data
   - AI latency <= 3 seconds
   - Missing performance metrics (never invent missing values)
   - Component verification for Futuristic Gaming AI HUD layout
"""

import time
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import init_db, save_session, get_session_by_id, get_all_memories, get_all_sessions
from app.fast_plan_engine import FastPlanEngine, default_fast_plan_engine
from app.models import FastPlanResponse, CurrentPerformance
from app.session_storage import SessionStorage


class TestPhase13HackathonDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        init_db()

    def test_01_complete_dashboard_flow_end_to_end(self):
        """
        Tests the entire 8-step core experience flow:
        GAME DETECTED -> MAP DETECTED -> PLAYER CONFIRMS -> AI PRE-GAME PLAN (< 3s)
        -> START SESSION -> LIVE PERFORMANCE -> SESSION COMPLETE -> MEMORY UPDATED
        """
        # Step 1 & 2: Detect Game & Map
        det_res = self.client.post("/api/detection/detect", json={
            "game": "BGMI",
            "map": "Erangel",
            "game_mode": "Classic",
            "source": "simulated"
        })
        self.assertEqual(det_res.status_code, 200)
        det_data = det_res.json()
        self.assertEqual(det_data["game"], "BGMI")
        self.assertEqual(det_data["map"], "Erangel")

        # Step 3: Player Confirms
        unique_sid = f"flow-session-{int(time.time() * 1000)}"
        conf_res = self.client.post("/api/detection/confirm", json={
            "session_id": unique_sid,
            "game": "BGMI",
            "map": "Erangel",
            "game_mode": "Classic"
        })
        self.assertEqual(conf_res.status_code, 200)

        # Step 4: AI Pre-Game Plan (< 3 seconds)
        t0 = time.perf_counter()
        plan_res = self.client.post("/api/dashboard/fast-plan", json={
            "game": "BGMI",
            "map": "Erangel",
            "game_mode": "Classic"
        })
        latency_sec = time.perf_counter() - t0
        self.assertEqual(plan_res.status_code, 200)
        self.assertLess(latency_sec, 3.0, "Plan generation must appear in approximately <= 3 seconds")

        plan_data = plan_res.json()
        self.assertIn("goal", plan_data)
        self.assertIn("focus_area", plan_data)
        self.assertEqual(plan_data["duration"], 60)
        self.assertEqual(plan_data["warmup"], 10)
        self.assertEqual(plan_data["gameplay"], 40)
        self.assertEqual(plan_data["review"], 10)
        self.assertGreaterEqual(len(plan_data["strategy"]), 3)
        self.assertLessEqual(len(plan_data["strategy"]), 5)

        # Step 5: Start Session
        start_res = self.client.post("/api/realtime/start", json={
            "session_id": unique_sid,
            "game": "BGMI",
            "map": "Erangel"
        })
        self.assertEqual(start_res.status_code, 200)
        start_data = start_res.json()
        self.assertEqual(start_data["kills"], 0)
        self.assertEqual(start_data["deaths"], 0)

        # Step 6: Live Performance Telemetry
        ev_kill = self.client.post("/api/realtime/event", json={
            "event_type": "kill",
            "details": {"count": 2, "score": 200}
        })
        self.assertEqual(ev_kill.status_code, 200)

        ev_death = self.client.post("/api/realtime/event", json={
            "event_type": "death",
            "details": {"count": 1}
        })
        self.assertEqual(ev_death.status_code, 200)

        perf_res = self.client.get("/api/realtime/performance")
        self.assertEqual(perf_res.status_code, 200)
        live_data = perf_res.json()
        self.assertEqual(live_data["kills"], 2)
        self.assertEqual(live_data["deaths"], 1)
        self.assertEqual(live_data["kd_ratio"], 2.0)

        # Step 7: End Session & Post-Session Complete
        complete_res = self.client.post("/api/dashboard/session/complete", json={
            "session_id": unique_sid,
            "game": "BGMI",
            "map": "Erangel",
            "kills": 8,
            "deaths": 4,
            "assists": 2,
            "duration_mins": 28,
            "result": "Win",
            "plan_id": plan_data["plan_id"]
        })
        self.assertEqual(complete_res.status_code, 200)
        complete_data = complete_res.json()

        # Step 8: Memory Updated & Session Stored
        self.assertEqual(complete_data["status"], "SESSION COMPLETE")
        self.assertIn("MEMORY UPDATED", complete_data["message"])
        self.assertEqual(complete_data["kd_ratio"], 2.0)
        self.assertEqual(complete_data["kills"], 8)
        self.assertEqual(complete_data["deaths"], 4)
        self.assertIsNotNone(complete_data["memory_id"])

    def test_02_bgmi_erangel_plan_and_evidence(self):
        """
        Test Case 1: BGMI + Erangel
        Verifies tactical rotation focus, quick strategy (3-5 actions),
        and grounded evidence.
        """
        # Ensure at least 2 sessions exist for BGMI Erangel
        save_session({
            "session_id": "bgmi-test-1",
            "game": "BGMI",
            "map": "Erangel",
            "kills": 6,
            "deaths": 2,
            "kd_ratio": 3.0,
            "result": "Win",
            "player_notes": "Rotation through open field caused zone damage."
        })
        save_session({
            "session_id": "bgmi-test-2",
            "game": "BGMI",
            "map": "Erangel",
            "kills": 4,
            "deaths": 3,
            "kd_ratio": 1.33,
            "result": "Top 10",
            "player_notes": "Covered rotation along ridge was successful."
        })

        res = self.client.post("/api/dashboard/fast-plan", json={
            "game": "BGMI",
            "map": "Erangel"
        })
        self.assertEqual(res.status_code, 200)
        plan = res.json()

        self.assertEqual(plan["game"], "BGMI")
        self.assertEqual(plan["map"], "Erangel")
        self.assertIn("Rotation Decisions", plan["focus_area"])
        self.assertFalse(plan["is_generic"])
        self.assertGreaterEqual(len(plan["strategy"]), 3)
        self.assertLessEqual(len(plan["strategy"]), 5)
        self.assertTrue(any("rotation" in s.lower() for s in plan["strategy"]))
        self.assertGreaterEqual(len(plan["evidence_session_ids"]), 2)

    def test_03_valorant_ascent_plan_and_evidence(self):
        """
        Test Case 2: Valorant + Ascent
        Verifies Ascent tactical focus, retake positioning, and evidence grounding.
        """
        save_session({
            "session_id": "val-test-1",
            "game": "Valorant",
            "map": "Ascent",
            "kills": 18,
            "deaths": 10,
            "kd_ratio": 1.8,
            "result": "Win",
            "player_notes": "Mid market dry peek punished by Operator."
        })
        save_session({
            "session_id": "val-test-2",
            "game": "Valorant",
            "map": "Ascent",
            "kills": 12,
            "deaths": 11,
            "kd_ratio": 1.09,
            "result": "Defeat",
            "player_notes": "Retake synergy on A site was disorganized."
        })

        res = self.client.post("/api/dashboard/fast-plan", json={
            "game": "Valorant",
            "map": "Ascent"
        })
        self.assertEqual(res.status_code, 200)
        plan = res.json()

        self.assertEqual(plan["game"], "Valorant")
        self.assertEqual(plan["map"], "Ascent")
        self.assertIn("Mid Control & Retake Synergy", plan["focus_area"])
        self.assertFalse(plan["is_generic"])
        self.assertGreaterEqual(len(plan["strategy"]), 3)
        self.assertGreaterEqual(len(plan["evidence_session_ids"]), 2)

    def test_04_incomplete_historical_data_insufficient_data(self):
        """
        Test Case 3: Incomplete historical data (< 2 sessions for game)
        Must NOT create fake personalized weaknesses.
        Must show:
        LIMITED DATA
        Not enough data to create a personalized strategy yet.
        We'll learn from this session.
        Clearly labeled: GENERAL SESSION PLAN
        """
        unique_game = f"UniqueGame_{int(time.time() * 1000)}"
        # Save only 1 session (insufficient for pattern/personalization)
        save_session({
            "session_id": "single-sess-1",
            "game": unique_game,
            "map": "MapAlpha",
            "kills": 3,
            "deaths": 2,
            "kd_ratio": 1.5,
            "result": "Win"
        })

        res = self.client.post("/api/dashboard/fast-plan", json={
            "game": unique_game,
            "map": "MapAlpha"
        })
        self.assertEqual(res.status_code, 200)
        plan = res.json()

        self.assertTrue(plan["is_generic"])
        self.assertEqual(plan["notice_title"], "LIMITED DATA")
        self.assertIn("Not enough data to create a personalized strategy yet", plan["notice_message"])
        self.assertEqual(plan["plan_label"], "GENERAL SESSION PLAN")

    def test_05_no_historical_data(self):
        """
        Test Case 4: No historical data (0 sessions)
        Returns GENERAL SESSION PLAN with LIMITED DATA banner.
        Does not crash or invent false history.
        """
        res = self.client.post("/api/dashboard/fast-plan", json={
            "game": "BrandNewUnplayedGame",
            "map": "VoidMap"
        })
        self.assertEqual(res.status_code, 200)
        plan = res.json()

        self.assertTrue(plan["is_generic"])
        self.assertEqual(plan["notice_title"], "LIMITED DATA")
        self.assertEqual(plan["plan_label"], "GENERAL SESSION PLAN")
        self.assertEqual(len(plan["evidence_session_ids"]), 0)

    def test_06_fast_plan_latency_under_3_seconds(self):
        """
        Test Case 5: 3-Second Performance Requirement
        Target: Plan generation latency <= 3 seconds.
        """
        start = time.perf_counter()
        res = self.client.post("/api/dashboard/fast-plan", json={
            "game": "BGMI",
            "map": "Erangel"
        })
        elapsed = time.perf_counter() - start
        self.assertEqual(res.status_code, 200)
        self.assertLess(elapsed, 3.0, f"Latency {elapsed:.3f}s exceeded 3-second limit")

        plan = res.json()
        self.assertLess(plan["generation_time_ms"], 3000.0)

    def test_07_missing_performance_metrics_not_invented(self):
        """
        Test Case 6 & 7: Missing performance metrics
        Verifies that only metrics that actually exist are displayed,
        and missing metrics are not replaced with invented values.
        """
        from app.realtime_analyzer import RealtimePerformanceAnalyzer
        analyzer = RealtimePerformanceAnalyzer()
        analyzer.start_session(session_id="test-incomplete", game="BGMI", map_name="Erangel")

        # Process a simple kill event without accuracy or damage
        analyzer.process_event({
            "event_type": "kill",
            "details": {"count": 1}
        })
        perf = analyzer.get_current_performance()

        self.assertEqual(perf.kills, 1)
        self.assertEqual(perf.deaths, 0)
        self.assertEqual(perf.kd_ratio, 1.0)
        # Verify objective_progress and current_score remain None if unprovided
        self.assertIsNone(perf.objective_progress)
        self.assertIsNone(perf.current_score)

    def test_08_dashboard_overview_aggregator(self):
        """
        Verifies /api/dashboard/overview returns all data needed by Cockpit HUD:
        - current_game, current_map, current_mode
        - session_status, ai_status
        - recent_sessions (for trend chart)
        - recent_memories (compact cards)
        - ai_insights (cross-session patterns)
        """
        res = self.client.get("/api/dashboard/overview?game=BGMI&map=Erangel")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "online")
        self.assertEqual(data["current_game"], "BGMI")
        self.assertEqual(data["current_map"], "Erangel")
        self.assertIn("session_status", data)
        self.assertIn("ai_status", data)
        self.assertIsInstance(data["recent_sessions"], list)
        self.assertIsInstance(data["recent_memories"], list)
        self.assertIsInstance(data["ai_insights"], list)

    def test_09_ask_your_gaming_brain_intelligence(self):
        """
        Verifies Ask Your Gaming Brain returns structured response:
        ANSWER, EVIDENCE, INSIGHT, RECOMMENDATION
        strictly grounded in stored sessions.
        """
        res = self.client.post("/api/intelligence/ask", json={
            "question": "When did I perform best?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("answer", data)
        self.assertIn("evidence", data)
        self.assertIn("insight", data)
        self.assertIn("recommendation", data)
        self.assertIsInstance(data["evidence"], list)

    def test_10_cockpit_html_components_and_layout(self):
        """
        Verifies the HTML template contains all required HUD elements:
        - Header: GAMING SECOND BRAIN, AI Memory & Performance Copilot
        - Status Bar: Game, Map, Session, AI
        - Game Detection Card (GAME DETECTED, CONFIRMED, START SESSION)
        - 3-Second AI Pre-Game Plan Card (TODAY'S FOCUS, SESSION, WARM-UP, GAMEPLAY, REVIEW, QUICK STRATEGY, WHY THIS PLAN?)
        - Live Performance Card (K/D, KILLS, DEATHS, SCORE, TIME)
        - Performance Trend Chart (Canvas element)
        - AI Insights Panel
        - Recent Memory section
        - Ask Your Gaming Brain search
        - Post-Session Modal (SESSION COMPLETE, Performance recorded, MEMORY UPDATED)
        """
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Header
        self.assertIn("GAMING SECOND BRAIN", html)
        self.assertIn("AI Memory &amp; Performance Copilot", html.replace("&", "&amp;"))

        # 2. Game Detection Card
        self.assertIn("GAME DETECTED", html)
        self.assertIn("CONFIRMED", html)
        self.assertIn("START SESSION", html)

        # 3. AI Pre-Game Plan Card
        self.assertIn("AI PRE-GAME PLAN", html)
        self.assertIn("TODAY'S FOCUS", html)
        self.assertIn("QUICK STRATEGY", html)
        self.assertIn("WHY THIS PLAN?", html)
        self.assertIn("START PLAN", html)

        # 4. Live Performance Card
        self.assertIn("LIVE PERFORMANCE", html)
        self.assertIn("live-metric-kd", html)
        self.assertIn("live-metric-kills", html)
        self.assertIn("live-metric-deaths", html)
        self.assertIn("live-metric-time", html)

        # 5. Trend Chart
        self.assertIn("PERFORMANCE TREND", html)
        self.assertIn("performanceTrendChart", html)

        # 6. AI Insights Panel
        self.assertIn("AI INSIGHTS", html)

        # 7. Recent Memory
        self.assertIn("RECENT MEMORY", html)

        # 8. Ask Your Gaming Brain
        self.assertIn("ASK YOUR GAMING BRAIN", html)

        # 9. Post-Session Modal
        self.assertIn("SESSION COMPLETE", html)
        self.assertIn("Performance recorded.", html)
        self.assertIn("MEMORY UPDATED", html)
        self.assertIn("VIEW ANALYSIS", html)
        self.assertIn("NEXT GAMING PLAN", html)


if __name__ == "__main__":
    unittest.main()
