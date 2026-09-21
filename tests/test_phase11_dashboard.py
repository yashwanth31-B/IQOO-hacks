import os
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, clear_all_data, save_session
from app.session_lifecycle import default_lifecycle_manager
from app.gaming_plan_engine import default_gaming_plan_engine


class TestPhase11Dashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.html_path = os.path.join(cls.base_dir, "static", "index.html")
        cls.js_path = os.path.join(cls.base_dir, "static", "js", "app.js")
        cls.charts_path = os.path.join(cls.base_dir, "static", "js", "charts.js")

    def setUp(self):
        default_lifecycle_manager.reset_to_idle()

    # -------------------------------------------------------------
    # 1. HEADER REQUIREMENTS VERIFICATION
    # -------------------------------------------------------------
    def test_header_branding_and_demo_flow(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Brand header: GAMING SECOND BRAIN and AI Gaming Copilot Memory Layer
        self.assertIn("GAMING SECOND BRAIN", html)
        self.assertIn("AI Gaming Copilot Memory Layer", html)

        # Interactive Demo Flow: DETECT -> START -> PLAY -> REMEMBER -> ASK -> ANALYZE -> PLAN
        self.assertIn("flow-step-detect", html)
        self.assertIn("flow-step-start", html)
        self.assertIn("flow-step-play", html)
        self.assertIn("flow-step-remember", html)
        self.assertIn("flow-step-ask", html)
        self.assertIn("flow-step-analyze", html)
        self.assertIn("flow-step-plan", html)
        self.assertIn("btn-run-demo-flow", html)

    # -------------------------------------------------------------
    # 2. CURRENT SESSION HUD (6 REQUIRED TELEMETRY FIELDS)
    # -------------------------------------------------------------
    def test_current_session_hud_telemetry_fields(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # All 6 required fields present in current session widget
        self.assertIn("hud-game-val", html, "Game telemetry element must exist")
        self.assertIn("hud-map-val", html, "Map telemetry element must exist")
        self.assertIn("hud-mode-val", html, "Mode telemetry element must exist")
        self.assertIn("hud-timer-val", html, "Timer telemetry element must exist")
        self.assertIn("hud-kd-val", html, "K/D telemetry element must exist")
        self.assertIn("hud-result-val", html, "Result telemetry element must exist")

        # Session lifecycle controls
        self.assertIn("btn-lifecycle-start-gaming", html)
        self.assertIn("btn-lifecycle-start-session", html)
        self.assertIn("btn-lifecycle-end-session", html)
        self.assertIn("btn-lifecycle-post-match", html)

    # -------------------------------------------------------------
    # 3. RECENT MEMORIES SECTION
    # -------------------------------------------------------------
    def test_recent_memories_section(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("RECENT MEMORIES", html)
        self.assertIn("dashboard-recent-memories", html)

        # Verify JS renderer populates game, map, K/D, duration, result, AI summary
        with open(self.js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("renderRecentMemories", js)
        self.assertIn("dashboard-recent-memories", js)
        self.assertIn("aiSummary", js)

    # -------------------------------------------------------------
    # 4. PERFORMANCE TREND SECTION
    # -------------------------------------------------------------
    def test_performance_trend_section(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()




        self.assertIn("PERFORMANCE TREND", html)
        self.assertIn("chart-kd-trend", html)
        self.assertIn("performance-trend-bars", html)

        with open(self.charts_path, "r", encoding="utf-8") as f:
            charts_js = f.read()
        self.assertIn("renderKdTrendChart", charts_js)

        with open(self.js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("renderPerformanceTrend", app_js)
        # Visual benchmark sessions 14-18
        self.assertIn("Session 14", app_js)
        self.assertIn("Session 18", app_js)

    # -------------------------------------------------------------
    # 5. ASK YOUR GAMING BRAIN SECTION (4 DISTINCT BLOCKS)
    # -------------------------------------------------------------
    def test_ask_your_gaming_brain_section(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("ASK YOUR GAMING BRAIN", html)
        self.assertIn("input-ask-gaming-brain", html)
        self.assertIn("btn-ask-gaming-brain", html)
        self.assertIn("When did I perform best?", html)

        # 4 Output blocks
        self.assertIn("brain-answer-val", html, "ANSWER block must exist")
        self.assertIn("brain-evidence-val", html, "EVIDENCE block must exist")
        self.assertIn("brain-insight-val", html, "INSIGHT block must exist")
        self.assertIn("brain-recommendation-val", html, "RECOMMENDATION block must exist")

        with open(self.js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("askGamingBrain", app_js)

    # -------------------------------------------------------------
    # 6. AI GAMING PLAN SECTION
    # -------------------------------------------------------------
    def test_ai_gaming_plan_section(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("AI GAMING PLAN", html)
        self.assertIn("plan-goal-val", html, "Goal element must exist")
        self.assertIn("plan-focus-val", html, "Focus element must exist")
        self.assertIn("plan-duration-val", html, "Duration element must exist")
        self.assertIn("plan-practice-val", html, "Practice element must exist")
        self.assertIn("plan-gameplay-val", html, "Gameplay element must exist")
        self.assertIn("plan-review-val", html, "Review element must exist")

        with open(self.js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("renderAIGamingPlan", app_js)

    # -------------------------------------------------------------
    # 7. BACKEND API INTEGRATION CHECKS FOR DASHBOARD
    # -------------------------------------------------------------
    def test_backend_apis_powering_dashboard(self):
        # 1. Sessions endpoint provides required fields for Recent Memories
        res_sess = self.client.get("/api/sessions")
        self.assertEqual(res_sess.status_code, 200)
        sessions = res_sess.json()
        self.assertIsInstance(sessions, list)
        self.assertGreater(len(sessions), 0)
        first_sess = sessions[0]
        self.assertIn("game", first_sess)
        self.assertIn("result", first_sess)

        # 2. Natural Language Search powers "Ask Your Gaming Brain"
        res_search = self.client.post("/api/search/natural-language", json={"query": "When did I perform best?"})
        self.assertEqual(res_search.status_code, 200)
        search_data = res_search.json()
        self.assertIn("answer", search_data)
        self.assertIn("evidence_session_ids", search_data)
        self.assertIn("evidence_sessions", search_data)

        # 3. AI Gaming Plan endpoint powers AI Gaming Plan panel
        res_plan = self.client.get("/api/plan/latest")
        self.assertEqual(res_plan.status_code, 200)
        plan_data = res_plan.json()
        self.assertIn("goal", plan_data)
        self.assertIn("focus_area", plan_data)
        self.assertIn("recommended_duration", plan_data)
        self.assertIn("practice_tasks", plan_data)
        self.assertIn("gameplay_tasks", plan_data)
        self.assertIn("review_tasks", plan_data)

        # 4. Lifecycle status powers Current Session HUD
        res_life = self.client.get("/api/lifecycle/status")
        self.assertEqual(res_life.status_code, 200)
        life_data = res_life.json()
        self.assertIn("state", life_data)


if __name__ == "__main__":
    unittest.main()
