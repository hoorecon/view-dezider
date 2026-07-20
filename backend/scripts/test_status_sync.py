import requests, uuid

BASE = "http://localhost:8001/api"
r = requests.post(f"{BASE}/auth/login", json={"email": "super@test.com", "password": "SuperPass2026!"})
print("login", r.status_code)
tok = r.json().get("session_token")
H = {"Authorization": f"Bearer {tok}"}

# 1) create manual action item
ai = requests.post(f"{BASE}/action-items", json={
    "source_module": "MANUAL", "title": "Sync test " + uuid.uuid4().hex[:6],
    "status": "pending", "recurrence_type": "one_time",
}, headers=H).json()
aid = ai["action_id"]
print("created", aid, "status", ai["status"], "progress", ai["progress_pct"])

# 2) update status -> wip_50, expect progress 50
u = requests.put(f"{BASE}/action-items/{aid}", json={"status": "wip_50"}, headers=H).json()
print("after wip_50 -> status", u["status"], "progress", u["progress_pct"])
assert u["status"] == "wip_50" and u["progress_pct"] == 50

# 3) port to CTT
p = requests.post(f"{BASE}/action-items/{aid}/port-to-ctt", headers=H).json()
task_id = p["ctt_task"]["task_id"]
print("ported to CTT task", task_id, "ctt status", p["ctt_task"]["status"])

# 4) forward sync: set action item done -> CTT current_status should become done
requests.put(f"{BASE}/action-items/{aid}", json={"status": "done"}, headers=H)
t = requests.get(f"{BASE}/ctt/tasks/{task_id}", headers=H).json()
print("forward sync: CTT current_status", t.get("current_status"))
assert t.get("current_status") == "done"

# 5) reverse sync: set CTT current_status wip_25 -> action item should become wip_25
requests.put(f"{BASE}/ctt/tasks/{task_id}", json={"current_status": "wip_25"}, headers=H)
a2 = requests.get(f"{BASE}/action-items/{aid}", headers=H).json()
print("reverse sync: action item status", a2.get("status"), "progress", a2.get("progress_pct"))
assert a2.get("status") == "wip_25" and a2.get("progress_pct") == 25

print("ALL SYNC TESTS PASSED")
