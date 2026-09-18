"""
Test Solution Finder Q2 AI auto-fill root causes endpoint contract, estimates & metering.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from starlette.testclient import TestClient
from server import app
from core.auth import get_current_user

mock_user = {"user_id": "test_user_rca_123", "email": "test@example.com", "role": "user"}


async def override_get_current_user():
    return mock_user


app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)


class TestSolutionFinderRCAAI:
    def test_estimates_contains_rcas_feature(self):
        """GET /api/ai-wallet/estimates includes solution_finder_rcas."""
        r = client.get("/api/ai-wallet/estimates")
        assert r.status_code == 200, r.text
        data = r.json()
        feats = data.get("features", {})
        assert "solution_finder_rcas" in feats
        assert "solution_finder_solutions" in feats
        assert "solution_finder_risks" in feats

    def test_suggest_root_causes_unauthorized(self):
        """POST /api/solution-finders/ai/suggest-root-causes without auth returns 401."""
        app.dependency_overrides.pop(get_current_user, None)
        try:
            r = client.post(
                "/api/solution-finders/ai/suggest-root-causes",
                json={"primary_concerns": [{"concern_id": "c1", "text": "High operational cost"}]},
            )
            assert r.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = override_get_current_user

    def test_suggest_root_causes_empty_concerns(self):
        """POST /api/solution-finders/ai/suggest-root-causes with empty concerns returns empty suggestions."""
        r = client.post(
            "/api/solution-finders/ai/suggest-root-causes",
            json={"primary_concerns": []},
        )
        assert r.status_code == 200
        assert r.json() == {"suggestions": {}}
