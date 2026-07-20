import requests
BASE="http://localhost:8001/api"
tok=requests.post(f"{BASE}/auth/login", json={"email":"super@test.com","password":"SuperPass2026!"}).json()["session_token"]
H={"Authorization":f"Bearer {tok}"}
TID="bmp-55-patterns"

# 1) Classify: mark Org Type + Affordability as quantitative (rest qualitative) via PUT
t=requests.get(f"{BASE}/decider-store/{TID}", headers=H).json()
factors=t["factors"]
for f in factors:
    f["factor_type"]="quantitative" if f["name"] in ("Org Type","Affordability") else "qualitative"
requests.put(f"{BASE}/decider-store/{TID}", json={"factors":factors}, headers=H)
print("classified: quant=", [f['name'] for f in factors if f['factor_type']=='quantitative'])

# 2) Push to stores
p=requests.post(f"{BASE}/decider-store/{TID}/push-to-stores", headers=H)
print("PUSH:", p.status_code, p.json())

# 3) Verify a solution created with quant factors + STRATEGY type
t2=requests.get(f"{BASE}/decider-store/{TID}", headers=H).json()
opt0=t2["options"][0]
sid=opt0.get("linked_solution_id")
print("opt0", opt0["name"], "linked_solution_id:", sid)
sol=requests.get(f"{BASE}/solutions-store/solutions/{sid}", headers=H).json()
print("SOLUTION type:", sol.get("type"), "| quant factors:", [(q['name'],q['value']) for q in sol.get('quantitative_factors',[])], "| decider_template_id:", sol.get("decider_template_id"))

# 4) Verify ReviewNet baseline
rv=requests.get(f"{BASE}/review-net/reviews", params={"solution_id":sid}, headers=H)
print("REVIEWNET reviews:", rv.status_code)
if rv.status_code==200:
    items=rv.json().get("items",[])
    base=[i for i in items if i.get("is_baseline")]
    print("  baseline present:", bool(base), "| factor_ratings sample:", (base[0]["factor_ratings"] if base else None))
    print("  baseline_profile keys:", list((base[0].get("baseline_profile") or {}).keys())[:4] if base else None)

# 5) Sync from stores (reverse)
s=requests.post(f"{BASE}/decider-store/{TID}/sync-from-stores", headers=H)
print("SYNC:", s.status_code, s.json())

# 6) from-solutions: build a new template from the pushed solutions
sids=[o["linked_solution_id"] for o in t2["options"][:3] if o.get("linked_solution_id")]
fs=requests.post(f"{BASE}/decider-store/from-solutions", json={"solution_ids":sids,"title":"BMP subset (from Store)","category":"Business"}, headers=H)
print("FROM-SOLUTIONS:", fs.status_code, fs.json())

# 7) STRATEGY type accepted by solutions create
sc=requests.post(f"{BASE}/solutions-store/solutions", json={"type":"STRATEGY","name":"Test Strategy","visibility":"PRIVATE"}, headers=H)
print("STRATEGY create:", sc.status_code, sc.json().get("type") if sc.status_code==200 else sc.text[:120])
print("BRIDGE TESTS DONE")
