"""
Unit and Integration Tests for Phase 14 Cloud Integration
Verifies Health Check Endpoints, Cyber HUD Routing, and Production CORS Configuration
"""

import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestCloudIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check_endpoint(self):
        """GET /health returns 200 OK and healthy status"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "gaming-second-brain")

    def test_api_health_check_endpoint(self):
        """GET /api/health returns 200 OK and healthy status"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "gaming-second-brain")

    def test_hud_routes(self):
        """GET /hud and GET /cyber-hud route to Cyber HUD cockpit"""
        res_hud = self.client.get("/hud")
        self.assertEqual(res_hud.status_code, 200)

        res_cyber_hud = self.client.get("/cyber-hud")
        self.assertEqual(res_cyber_hud.status_code, 200)

        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)

    def test_cors_preflight_for_production_vercel(self):
        """CORS preflight request from production Vercel frontend is allowed"""
        headers = {
            "Origin": "https://ai-gaming-copilot.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = self.client.options("/api/status", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://ai-gaming-copilot.vercel.app"
        )

    def test_cors_headers_on_api_request(self):
        """GET request with Vercel origin returns matching access-control-allow-origin"""
        headers = {
            "Origin": "https://ai-gaming-copilot.vercel.app"
        }
        response = self.client.get("/api/status", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://ai-gaming-copilot.vercel.app"
        )


if __name__ == "__main__":
    unittest.main()
