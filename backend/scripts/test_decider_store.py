import requests
BASE="http://localhost:8001/api"

# public (no auth)
r=requests.get(f"{BASE}/decider-store"); print("PUBLIC list", r.status_code, "count", len(r.json().get("templates",[])))
print("  card:", {k:r.json()['templates'][0][k] for k in ('title','factor_count','option_count','pricing_type','allowed_clone_modes')})
m=requests.get(f"{BASE}/decider-store/meta"); print("META", m.status_code, m.json())
d=requests.get(f"{BASE}/decider-store/bmp-55-patterns"); print("PUBLIC detail", d.status_code, "factors", len(d.json().get('factors',[])), "options", len(d.json().get('options',[])))
tpl=requests.get(f"{BASE}/decider-store/import-template.xlsx"); print("TEMPLATE xlsx", tpl.status_code, "bytes", len(tpl.content), tpl.headers.get('content-type','')[:40])

# login
tok=requests.post(f"{BASE}/auth/login", json={"email":"super@test.com","password":"SuperPass2026!"}).json()["session_token"]
H={"Authorization":f"Bearer {tok}"}

# clone FULL
cf=requests.post(f"{BASE}/decider-store/bmp-55-patterns/clone", json={"mode":"full"}, headers=H).json()
print("CLONE full:", cf)
dec=requests.get(f"{BASE}/decisions/{cf['decision_id']}", headers=H).json()
print("  decision factors:", len(dec['factors']), "options:", len(dec['options']))
f0=dec['factors'][0]; print("  factor0 full: category=",f0['category'],"rating=",f0['rating'],"name=",f0['name'])
o0=dec['options'][0]; print("  option0:", o0['name'], "assessments:", len(o0['assessments']))
print("  assess sample unit_value:", o0['assessments'][0].get('unit_value'), "| pct:", o0['assessments'][0].get('percentage'))

# clone VALUES_ONLY
cv=requests.post(f"{BASE}/decider-store/bmp-55-patterns/clone", json={"mode":"values_only"}, headers=H).json()
decv=requests.get(f"{BASE}/decisions/{cv['decision_id']}", headers=H).json()
fv0=decv['factors'][0]; print("CLONE values_only: factor0 category=",repr(fv0['category']),"rating=",fv0['rating'],"(should be '' and 0)")
print("  options:", len(decv['options']), "opt0 assessments:", len(decv['options'][0]['assessments']))
print("ALL DECIDER STORE TESTS DONE")
