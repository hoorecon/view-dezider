"""
Regression — Daily Time Log + Time Dezider + Time Store.
"""
import os
import sys
import time
import requests
from datetime import datetime

BASE = os.environ.get("BASE_URL", "http://localhost:8001")
API = f"{BASE}/api"


class R:
    def __init__(self): self.p = 0; self.f = 0; self.errs = []
    def ok(self, c, label, detail=""):
        if c: self.p += 1; print(f"  OK  {label}")
        else:
            self.f += 1; self.errs.append(f"{label}: {detail}")
            print(f"  FAIL {label}{(' - ' + detail) if detail else ''}")
    def done(self):
        t = self.p + self.f
        print(f"\n{'='*70}\nDTL + Time Dezider + Time Store — {self.p}/{t} passed\n{'='*70}")
        if self.errs:
            for e in self.errs: print(f"  - {e}")
        return self.f == 0


def main():
    r = R()
    print("\n" + "="*70 + "\n Daily Time Log + Time Dezider + Time Store\n" + "="*70)

    # Fresh user
    email = f"dtl_{int(time.time())}@example.com"
    res = requests.post(f"{API}/auth/register",
                        json={"email": email, "password": "DTLPass2026!", "name": "DTL Tester"},
                        timeout=10)
    r.ok(res.status_code == 200, "register", f"status={res.status_code}")
    token = res.json().get("session_token", "")
    H = {"Authorization": f"Bearer {token}"}
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # ---------- Daily Time Log ----------
    print("\n[DTL] Preferences + 4 key timings")
    res = requests.get(f"{API}/daily-time-log/preferences", headers=H, timeout=5)
    r.ok(res.status_code == 200, "GET preferences")
    d = res.json()
    for k in ("wake_up", "bed_time", "business_start", "business_end"):
        r.ok(k in d, f"preferences has {k}")

    res = requests.post(f"{API}/daily-time-log/preferences", headers=H,
                        json={"wake_up": "05:30", "bed_time": "23:00",
                              "business_start": "09:00", "business_end": "18:00",
                              "nudge_morning": True}, timeout=5)
    r.ok(res.status_code == 200 and res.json()["wake_up"] == "05:30",
         "POST preferences persists", f"got={res.json().get('wake_up')}")

    print("\n[DTL] Day upsert + get + refresh rollup + streak")
    # Upsert day with 2 manual blocks
    res = requests.post(f"{API}/daily-time-log", headers=H,
                        json={
                            "log_date": today,
                            "blocks": [
                                {"start": "06:00", "end": "07:00", "category": "lifestyle",
                                 "label": "Morning run"},
                                {"start": "09:30", "end": "11:00", "category": "ctt",
                                 "label": "Deep work block"},
                            ],
                            "overall_mood": 4, "overall_energy": 4,
                            "reflection": "Good start",
                        }, timeout=10)
    r.ok(res.status_code == 200, "POST upsert day")
    doc = res.json()
    r.ok(doc.get("total_logged_minutes", 0) == 60 + 90,
         "total_logged_minutes sums correctly (150)",
         f"got={doc.get('total_logged_minutes')}")

    res = requests.get(f"{API}/daily-time-log/{today}", headers=H, timeout=10)
    r.ok(res.status_code == 200 and len(res.json().get("blocks", [])) >= 2,
         "GET day returns >=2 blocks",
         f"blocks={len(res.json().get('blocks', []))}")
    pva = res.json().get("planned_vs_actual", {})
    r.ok((pva.get("per_category_minutes") or {}).get("ctt", 0) == 90,
         "CTT category rolled up to 90 min")

    res = requests.post(f"{API}/daily-time-log/{today}/refresh-rollup", headers=H,
                        json={}, timeout=10)
    r.ok(res.status_code == 200, "POST refresh-rollup")

    res = requests.get(f"{API}/daily-time-log/streaks", headers=H, timeout=5)
    r.ok(res.status_code == 200 and int(res.json().get("current", 0)) >= 1,
         "Streak >= 1 after first log",
         f"got={res.json()}")

    res = requests.get(f"{API}/daily-time-log/week", headers=H, timeout=5)
    r.ok(res.status_code == 200 and len(res.json().get("days", [])) == 7,
         "Week view returns 7 days")

    res = requests.get(f"{API}/daily-time-log/weekly-review", headers=H, timeout=5)
    r.ok(res.status_code == 200, "Weekly review returns 200")
    w = res.json()
    r.ok("variance_notes" in w and "total_logged_minutes" in w,
         "Weekly review has shape keys")

    # ---------- Time Dezider Raja Guru ----------
    print("\n[Time Dezider] Rule-based guidance (Raja Guru)")
    res = requests.get(f"{API}/raja-guru/day-plan", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "intro" in res.json(),
         "day-plan returns intro")
    res = requests.get(f"{API}/raja-guru/midday-check", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "picks" in res.json(),
         "midday-check returns picks field")
    res = requests.get(f"{API}/raja-guru/evening-retro", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "wins" in res.json() and "gaps" in res.json(),
         "evening-retro returns wins+gaps")
    res = requests.get(f"{API}/raja-guru/next-action", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "pick" in res.json(),
         "next-action returns pick field")

    res = requests.get(f"{API}/raja-guru/preferences", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "nudge_morning" in res.json(),
         "raja-guru preferences returns nudge flags")
    res = requests.post(f"{API}/raja-guru/preferences", headers=H,
                        json={"nudge_hourly": True}, timeout=5)
    r.ok(res.status_code == 200 and res.json().get("nudge_hourly") is True,
         "Toggle nudge_hourly=True persists")

    res = requests.post(f"{API}/raja-guru/feedback", headers=H,
                        json={"nudge_id": "test_nudge", "decision": "accept",
                              "action_ref_id": "tid", "action_ref_type": "ctt_task"},
                        timeout=5)
    r.ok(res.status_code == 200 and res.json().get("ok") is True,
         "Nudge feedback accept recorded")
    res = requests.post(f"{API}/raja-guru/feedback", headers=H,
                        json={"nudge_id": "x", "decision": "invalid"}, timeout=5)
    r.ok(res.status_code == 400, "Invalid decision returns 400")

    # ---------- Time Store ----------
    print("\n[Time Store] Audit + Services + Purchases + Delegations")
    res = requests.get(f"{API}/time-store/time-audit", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "opportunities" in res.json() and "total_minutes_saveable_per_week" in res.json(),
         "time-audit returns opportunities + total")

    res = requests.get(f"{API}/time-store/services?save_minutes_per_day=30", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "services" in res.json() and "buckets_per_day" in res.json(),
         "services returns services list + buckets")

    res = requests.get(f"{API}/time-store/purchases", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "items" in res.json(),
         "purchases returns items list (empty ok)")

    res = requests.get(f"{API}/time-store/delegations", headers=H, timeout=5)
    r.ok(res.status_code == 200 and "items" in res.json(),
         "delegations returns items list (empty ok)")

    res = requests.post(f"{API}/time-store/delegate", headers=H,
                        json={"source_type": "ctt_task", "source_id": "fake-task",
                              "description": "Delegate weekly expense filing",
                              "estimated_minutes_saved": 60},
                        timeout=5)
    r.ok(res.status_code == 200 and res.json().get("ok") is True,
         "delegate returns ok")

    res = requests.post(f"{API}/time-store/delegate", headers=H,
                        json={"source_type": "bogus", "source_id": "x",
                              "description": "x", "estimated_minutes_saved": 10},
                        timeout=5)
    r.ok(res.status_code == 400, "Bad source_type returns 400")

    res = requests.post(f"{API}/time-store/purchase", headers=H,
                        json={"solution_id": "does-not-exist",
                              "save_minutes_per_day": 30}, timeout=5)
    r.ok(res.status_code == 404, "Purchase unknown solution returns 404")

    return r.done()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
