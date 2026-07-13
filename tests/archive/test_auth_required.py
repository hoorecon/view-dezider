"""
Test that authentication is required on all AALA and LEE endpoints (except taxonomy/meta)
"""

import requests

BASE_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"

def test_auth_required():
    """Test that endpoints require authentication"""
    
    print("Testing authentication requirements...")
    print("=" * 80)
    
    # Endpoints that should NOT require auth
    public_endpoints = [
        ("GET", "/aala/taxonomy"),
        ("GET", "/lifestyle-eval/meta")
    ]
    
    # Endpoints that SHOULD require auth
    protected_endpoints = [
        ("POST", "/aala/assessments"),
        ("GET", "/aala/assessments"),
        ("GET", "/aala/assessments/test-id"),
        ("PUT", "/aala/assessments/test-id"),
        ("DELETE", "/aala/assessments/test-id"),
        ("GET", "/aala/dashboard"),
        ("GET", "/aala/for-solution-matrix"),
        ("GET", "/aala/trends"),
        ("POST", "/lifestyle-eval/logs"),
        ("GET", "/lifestyle-eval/logs/2026-05-03"),
        ("GET", "/lifestyle-eval/logs"),
        ("DELETE", "/lifestyle-eval/logs/2026-05-03"),
        ("GET", "/lifestyle-eval/summary"),
        ("GET", "/lifestyle-eval/planned-vs-actual"),
        ("GET", "/lifestyle-eval/dashboard")
    ]
    
    # Test public endpoints
    print("\n✅ Testing PUBLIC endpoints (should work without auth):")
    for method, endpoint in public_endpoints:
        url = f"{BASE_URL}{endpoint}"
        response = requests.request(method, url)
        status = "✅ PASS" if response.status_code in [200, 404] else "❌ FAIL"
        print(f"  {status}: {method} {endpoint} - Status: {response.status_code}")
    
    # Test protected endpoints
    print("\n🔒 Testing PROTECTED endpoints (should return 401 without auth):")
    for method, endpoint in protected_endpoints:
        url = f"{BASE_URL}{endpoint}"
        response = requests.request(method, url, json={})
        status = "✅ PASS" if response.status_code == 401 else "❌ FAIL"
        print(f"  {status}: {method} {endpoint} - Status: {response.status_code}")
    
    print("=" * 80)

if __name__ == "__main__":
    test_auth_required()
