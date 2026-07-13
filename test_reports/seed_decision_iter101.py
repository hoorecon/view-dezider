"""Seed a small (2 options x 4 factors = 8 cells) decision for the
Step 7 AI Assess All retest. Prints the decision id on stdout."""
import os, sys, json, requests

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
        or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
EMAIL = "harden_1777921741@example.com"
PWD = "HardenPass2026!"

s = requests.Session()
s.headers["Content-Type"] = "application/json"
r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=30)
assert r.status_code == 200, r.text
tok = r.json().get("session_token") or r.json().get("token")
s.headers["Authorization"] = f"Bearer {tok}"

# Create decision
r = s.post(f"{BASE}/api/decisions",
           json={"title": "TEST_FE_BulkAssess_Iter101",
                 "context": "Choosing a laptop for development & travel"},
           timeout=30)
assert r.status_code in (200, 201), r.text
did = r.json()["id"]

factors = [
    {"id": "f_battery", "name": "Battery life",
     "factor_type": "quantitative", "data_type": "numeric",
     "expected_value": "10", "operator": ">=", "unit": "hrs",
     "category": "primary", "rating": 8},
    {"id": "f_weight", "name": "Weight",
     "factor_type": "quantitative", "data_type": "numeric",
     "expected_value": "1.5", "operator": "<=", "unit": "kg",
     "category": "primary", "rating": 7},
    {"id": "f_price", "name": "Price",
     "factor_type": "quantitative", "data_type": "numeric",
     "expected_value": "120000", "operator": "<=", "unit": "INR",
     "category": "primary", "rating": 9},
    {"id": "f_screen", "name": "Screen quality",
     "factor_type": "qualitative", "data_type": "text",
     "expected_value": "excellent", "category": "secondary", "rating": 6},
]
options = [
    {"id": "o_macbook", "name": "MacBook Air M3", "assessments": []},
    {"id": "o_xps", "name": "Dell XPS 13", "assessments": []},
]
r = s.put(f"{BASE}/api/decisions/{did}",
          json={"factors": factors, "options": options}, timeout=30)
assert r.status_code == 200, r.text
print(json.dumps({"decision_id": did, "token": tok, "base": BASE}))
