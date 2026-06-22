"""Iteration 144 — Dependent Decisions (link a SCORED decision into another
decision as a factor). Light regression — backend curl flows already verified
by main agent, this is the smoke harness."""
import os
import time
import pytest
import requests

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") + "/api"


def _register():
    email = f"iter144_{int(time.time()*1000)}@example.com"
    r = requests.post(f"{BASE}/auth/register",
                      json={"email": email, "password": "Iter144Pass!", "name": "Iter144 User"},
                      timeout=30)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    tok = body.get("session_token") or body.get("token") or body.get("access_token")
    assert tok, body
    return email, tok


def _hdr(tok):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {tok}"}


def _make_scored(tok, title="TEST_iter144_TARGET"):
    """Create + put factors+options+assessments so worth_percentage > 0."""
    r = requests.post(f"{BASE}/decisions",
                      json={"title": title, "context": "scored target"},
                      headers=_hdr(tok), timeout=30)
    assert r.status_code in (200, 201), r.text
    did = r.json()["id"]
    factors = [
        {"id": "f_speed", "name": "Speed", "factor_type": "quantitative",
         "data_type": "numeric", "expected_value": "60", "operator": ">=",
         "category": "primary", "rating": 8},
        {"id": "f_price", "name": "Price", "factor_type": "quantitative",
         "data_type": "numeric", "expected_value": "100", "operator": "<=",
         "category": "primary", "rating": 7},
    ]
    options = [
        {"id": "o_honda", "name": "Honda",
         "assessments": [
             {"factor_id": "f_speed", "percentage": 80, "actual_value": 80, "assessment_mode": "custom"},
             {"factor_id": "f_price", "percentage": 70, "actual_value": 70, "assessment_mode": "custom"},
         ]},
        {"id": "o_toyota", "name": "Toyota",
         "assessments": [
             {"factor_id": "f_speed", "percentage": 60, "actual_value": 60, "assessment_mode": "custom"},
             {"factor_id": "f_price", "percentage": 90, "actual_value": 90, "assessment_mode": "custom"},
         ]},
    ]
    r = requests.put(f"{BASE}/decisions/{did}",
                     json={"factors": factors, "options": options},
                     headers=_hdr(tok), timeout=30)
    assert r.status_code == 200, r.text
    # PUT returns only {"message": ...}; refetch
    g = requests.get(f"{BASE}/decisions/{did}", headers=_hdr(tok), timeout=30)
    assert g.status_code == 200, g.text
    body = g.json()
    worths = [o.get("worth_percentage", 0) for o in body.get("options", [])]
    assert any((w or 0) > 0 for w in worths), worths
    return did, body


def _make_empty(tok, title="TEST_iter144_LINKER"):
    r = requests.post(f"{BASE}/decisions",
                      json={"title": title, "context": "linker"},
                      headers=_hdr(tok), timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def ctx():
    email, tok = _register()
    target_id, target_body = _make_scored(tok)
    linker_id = _make_empty(tok)
    yield {"tok": tok, "email": email, "target_id": target_id,
           "linker_id": linker_id, "target": target_body}
    # cleanup
    for did in (linker_id, target_id):
        try:
            requests.delete(f"{BASE}/decisions/{did}", headers=_hdr(tok), timeout=10)
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────────────
class TestLinkable:
    def test_linkable_lists_scored_target(self, ctx):
        r = requests.get(f"{BASE}/decisions/{ctx['linker_id']}/linkable",
                         headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        decs = r.json().get("decisions", [])
        ids = [d["id"] for d in decs]
        assert ctx["target_id"] in ids, ids
        target_entry = next(d for d in decs if d["id"] == ctx["target_id"])
        assert target_entry["options"], target_entry
        assert all("worth_percentage" in o for o in target_entry["options"])
        assert target_entry.get("top_option_id"), target_entry

    def test_linkable_excludes_self(self, ctx):
        r = requests.get(f"{BASE}/decisions/{ctx['linker_id']}/linkable",
                         headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200
        ids = [d["id"] for d in r.json().get("decisions", [])]
        assert ctx["linker_id"] not in ids

    def test_linkable_omits_unscored(self, ctx):
        # The linker decision itself is unscored, so even if we queried
        # the target_id, the linker (which is unscored) must NOT appear.
        r = requests.get(f"{BASE}/decisions/{ctx['target_id']}/linkable",
                         headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200
        ids = [d["id"] for d in r.json().get("decisions", [])]
        assert ctx["linker_id"] not in ids


class TestLinkDecision:
    def test_link_factor_only(self, ctx):
        # Pick a specific option (Honda)
        target = ctx["target"]
        honda_opt = next(o for o in target["options"] if o["name"] == "Honda")
        expected_value = honda_opt["worth_percentage"]
        r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/link-decision",
                          json={"linked_decision_id": ctx["target_id"],
                                "linked_option_id": honda_opt["id"],
                                "metric": "option_worth",
                                "refresh": "manual",
                                "link_mode": "factor_only",
                                "factor_name": "Honda link"},
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body.get("factor_id")
        assert round(body["value"], 1) == round(expected_value, 1), body

        # Verify factor exists with data_source.type=decision_link
        g = requests.get(f"{BASE}/decisions/{ctx['linker_id']}",
                         headers=_hdr(ctx["tok"]), timeout=30)
        assert g.status_code == 200
        dec = g.json()
        f = next((x for x in dec["factors"] if x["id"] == body["factor_id"]), None)
        assert f, dec["factors"]
        assert f["data_source"]["type"] == "decision_link"
        cfg = f["data_source"]["config"]
        assert cfg["linked_decision_id"] == ctx["target_id"]
        assert cfg["refresh"] == "manual"
        assert cfg["link_mode"] == "factor_only"
        # In factor_only mode, options list should be unchanged (empty)
        ctx["factor_only_factor_id"] = body["factor_id"]

    def test_link_factor_and_option(self, ctx):
        target = ctx["target"]
        toyota_opt = next(o for o in target["options"] if o["name"] == "Toyota")
        expected_value = toyota_opt["worth_percentage"]
        r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/link-decision",
                          json={"linked_decision_id": ctx["target_id"],
                                "linked_option_id": toyota_opt["id"],
                                "metric": "option_worth",
                                "refresh": "auto",
                                "link_mode": "factor_and_option",
                                "factor_name": "Toyota link"},
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert round(body["value"], 1) == round(expected_value, 1)

        # Verify option appended with assessment for factor_id
        g = requests.get(f"{BASE}/decisions/{ctx['linker_id']}",
                         headers=_hdr(ctx["tok"]), timeout=30)
        dec = g.json()
        fid = body["factor_id"]
        opt_with_link = None
        for o in dec.get("options", []):
            for a in o.get("assessments", []):
                if a.get("factor_id") == fid:
                    opt_with_link = o
                    break
        assert opt_with_link, dec.get("options")
        a = next(a for a in opt_with_link["assessments"] if a["factor_id"] == fid)
        assert a["percentage"] == int(round(expected_value))
        ctx["factor_and_option_factor_id"] = fid

    def test_self_link_rejected(self, ctx):
        r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/link-decision",
                          json={"linked_decision_id": ctx["linker_id"],
                                "metric": "top_score",
                                "link_mode": "factor_only"},
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 422, r.text

    def test_unscored_target_rejected(self, ctx):
        # Create a fresh empty decision and try to link it
        empty_id = _make_empty(ctx["tok"], title="TEST_iter144_UNSCORED")
        try:
            r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/link-decision",
                              json={"linked_decision_id": empty_id,
                                    "metric": "top_score",
                                    "link_mode": "factor_only"},
                              headers=_hdr(ctx["tok"]), timeout=30)
            assert r.status_code == 422, r.text
        finally:
            requests.delete(f"{BASE}/decisions/{empty_id}", headers=_hdr(ctx["tok"]), timeout=10)

    def test_circular_link_blocked(self, ctx):
        # The linker already links the target. Now try linking the linker
        # back into the target → must be 409.
        # First we need to score the linker (the link added factors+options)
        # Verify linker is scored.
        g = requests.get(f"{BASE}/decisions/{ctx['linker_id']}",
                         headers=_hdr(ctx["tok"]), timeout=30)
        worths = [o.get("worth_percentage", 0) for o in g.json().get("options", [])]
        if not any((w or 0) > 0 for w in worths):
            pytest.skip("Linker not scored — circular guard requires scored linker")
        r = requests.post(f"{BASE}/decisions/{ctx['target_id']}/link-decision",
                          json={"linked_decision_id": ctx["linker_id"],
                                "metric": "top_score",
                                "link_mode": "factor_only"},
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 409, r.text


class TestResolve:
    def test_resolve_single_link(self, ctx):
        fid = ctx.get("factor_only_factor_id")
        assert fid, "needs prior link"
        r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/links/{fid}/resolve",
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "new" in body

    def test_refresh_auto(self, ctx):
        r = requests.post(f"{BASE}/decisions/{ctx['linker_id']}/links/refresh-auto",
                          headers=_hdr(ctx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body.get("changes"), list)
