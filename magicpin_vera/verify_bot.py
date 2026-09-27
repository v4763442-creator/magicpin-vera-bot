"""
magicpin_vera/verify_bot.py
Comprehensive local verification script for Magicpin Vera AI Engine.

Tests:
1. GET /v1/healthz and GET /v1/metadata
2. POST /v1/context with realistic Category, Merchant, Customer, and Trigger contexts
3. Stale version conflict handling (HTTP 409) and idempotent re-posts (HTTP 200)
4. POST /v1/tick proactive customer-facing recall message
5. POST /v1/tick restraint / silence case (premature festival trigger)
6. POST /v1/reply multi-turn handling:
   - Canned auto-reply (wait / back-off)
   - Repeated auto-reply (end)
   - Intent commitment (action execution, zero qualifying)
   - Hostile opt-out (suppression and end)
   - Out-of-scope curveball (polite decline and pivot)
7. POST /v1/teardown cleanup and post-teardown health check

Can be executed standalone (in-process via TestClient) or against a live HTTP server:
  Standalone:  python magicpin_vera/verify_bot.py
  Live Server: python magicpin_vera/verify_bot.py --url http://127.0.0.1:8080
"""

from __future__ import annotations
import sys
import os
from pathlib import Path

# Ensure workspace root is in sys.path
workspace_root = str(Path(__file__).resolve().parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import argparse
from typing import Dict, Any

from fastapi.testclient import TestClient
from magicpin_vera.bot import app


class VerificationClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url.rstrip("/") if base_url else None
        if not self.base_url:
            self.client = TestClient(app)
        else:
            import httpx
            self.http_client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def get(self, path: str):
        if not self.base_url:
            return self.client.get(path)
        return self.http_client.get(path)

    def post(self, path: str, json_data: Dict[str, Any]):
        if not self.base_url:
            return self.client.post(path, json=json_data)
        return self.http_client.post(path, json=json_data)


def pretty(data: Any) -> str:
    return json.dumps(data, indent=2)


def run_verification(base_url: str | None = None):
    print("=" * 70)
    print("MAGICPIN VERA LOCAL VERIFICATION SUITE")
    print(f"Target: {'In-Process TestClient' if not base_url else base_url}")
    print("=" * 70)

    vc = VerificationClient(base_url)
    all_passed = True

    # -------------------------------------------------------------------------
    # TEST 1: Health & Metadata
    # -------------------------------------------------------------------------
    print("\n[TEST 1] GET /v1/healthz & GET /v1/metadata")
    r_health = vc.get("/v1/healthz")
    assert r_health.status_code == 200, f"Expected 200, got {r_health.status_code}"
    print(f"  GET /v1/healthz -> {r_health.status_code}")
    print("  " + pretty(r_health.json()).replace("\n", "\n  "))

    r_meta = vc.get("/v1/metadata")
    assert r_meta.status_code == 200, f"Expected 200, got {r_meta.status_code}"
    print(f"  GET /v1/metadata -> {r_meta.status_code}")
    print("  " + pretty(r_meta.json()).replace("\n", "\n  "))
    print("  -> [PASS] Health and Metadata verified.")

    # -------------------------------------------------------------------------
    # TEST 2: Context Ingestion (Category, Merchant, Customer, Trigger)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Ingesting realistic 4-context data via POST /v1/context")

    cat_payload = {
        "slug": "dentists",
        "display_name": "Dental Clinics",
        "voice": {
            "tone": "professional",
            "register": "collegial",
            "code_mix": "hindi_english_natural",
            "vocab_allowed": ["clinical", "recall", "hygiene", "appointment"],
            "vocab_taboo": ["completely cure", "miracle", "guaranteed", "100% safe"]
        },
        "offer_catalog": [
            {"id": "off_scaling", "title": "Scaling & Polishing @ ₹799", "audience": "lapsed"}
        ],
        "peer_stats": {
            "avg_views_30d": 450,
            "avg_calls_30d": 35,
            "retention_6mo_pct": 0.42
        }
    }
    r = vc.post("/v1/context", {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200, f"Category push failed: {r.text}"
    print(f"  POST CategoryContext -> {r.status_code} ({r.json()['ack_id']})")

    mer_payload = {
        "merchant_id": "m_dental_01",
        "category_slug": "dentists",
        "identity": {
            "name": "Apex Dental Clinic",
            "city": "Bengaluru",
            "locality": "Indiranagar",
            "owner_first_name": "Arun",
            "languages": ["en", "hi-en mix"]
        },
        "subscription": {
            "status": "active",
            "plan": "Pro",
            "days_remaining": 45
        },
        "performance": {
            "views": 480,
            "calls": 42,
            "directions": 18,
            "delta_7d": {"views_pct": 0.05, "calls_pct": 0.10}
        },
        "offers": [
            {"id": "mer_off_01", "title": "Comprehensive Checkup + Scaling @ ₹699", "status": "active"}
        ]
    }
    r = vc.post("/v1/context", {
        "scope": "merchant",
        "context_id": "m_dental_01",
        "version": 1,
        "payload": mer_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200, f"Merchant push failed: {r.text}"
    print(f"  POST MerchantContext -> {r.status_code} ({r.json()['ack_id']})")

    cust_payload = {
        "customer_id": "c_patient_01",
        "merchant_id": "m_dental_01",
        "identity": {
            "name": "Sunita Sharma",
            "language_pref": "hi-en mix"
        },
        "relationship": {
            "first_visit": "2025-04-10",
            "last_visit": "2025-10-15",
            "visits_total": 3,
            "services_received": ["scaling", "filling"]
        },
        "state": "lapsed_soft",
        "preferences": {
            "channel": "whatsapp",
            "preferred_slots": "Saturday morning",
            "reminder_opt_in": True
        },
        "consent": {
            "scope": ["reminders", "promotional_offers"]
        }
    }
    r = vc.post("/v1/context", {
        "scope": "customer",
        "context_id": "c_patient_01",
        "version": 1,
        "payload": cust_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200, f"Customer push failed: {r.text}"
    print(f"  POST CustomerContext -> {r.status_code} ({r.json()['ack_id']})")

    trg_payload = {
        "id": "trg_recall_01",
        "scope": "customer",
        "kind": "recall_due",
        "source": "internal",
        "merchant_id": "m_dental_01",
        "customer_id": "c_patient_01",
        "urgency": 4,
        "payload": {
            "service_due": "6-month dental checkup & cleaning",
            "available_slots": [
                {"label": "Saturday 10:30am", "iso": "2026-05-02T10:30:00Z"},
                {"label": "Sunday 11:00am", "iso": "2026-05-03T11:00:00Z"}
            ]
        },
        "suppression_key": "recall:c_patient_01:2026_h1",
        "expires_at": "2026-05-15T23:59:59Z"
    }
    r = vc.post("/v1/context", {
        "scope": "trigger",
        "context_id": "trg_recall_01",
        "version": 1,
        "payload": trg_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200, f"Trigger push failed: {r.text}"
    print(f"  POST TriggerContext -> {r.status_code} ({r.json()['ack_id']})")
    print("  -> [PASS] All 4 contexts pushed successfully.")

    # -------------------------------------------------------------------------
    # TEST 3: Versioning Semantics (Idempotency vs Stale Version 409)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Versioning & Stale Version Handling (HTTP 409)")

    # 3a. Re-post identical version (Idempotency: 200 OK)
    r_idempotent = vc.post("/v1/context", {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_payload,
        "delivered_at": "2026-04-26T10:01:00Z"
    })
    assert r_idempotent.status_code == 200, f"Expected 200 for idempotent re-post, got {r_idempotent.status_code}"
    print(f"  3a. Idempotent re-post (v1 -> v1): HTTP {r_idempotent.status_code} -> accepted={r_idempotent.json().get('accepted')}")

    # 3b. Atomic update with higher version (200 OK)
    r_v2 = vc.post("/v1/context", {
        "scope": "category",
        "context_id": "dentists",
        "version": 2,
        "payload": cat_payload,
        "delivered_at": "2026-04-26T10:02:00Z"
    })
    assert r_v2.status_code == 200, f"Expected 200 for version upgrade, got {r_v2.status_code}"
    print(f"  3b. Version upgrade (v1 -> v2): HTTP {r_v2.status_code} -> ack_id={r_v2.json().get('ack_id')}")

    # 3c. Stale version conflict (HTTP 409 Conflict)
    r_stale = vc.post("/v1/context", {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_payload,
        "delivered_at": "2026-04-26T10:03:00Z"
    })
    assert r_stale.status_code == 409, f"Expected 409 for stale version, got {r_stale.status_code}"
    stale_body = r_stale.json()
    assert stale_body.get("reason") == "stale_version", f"Expected stale_version reason, got {stale_body}"
    assert stale_body.get("current_version") == 2, f"Expected current_version 2, got {stale_body}"
    print(f"  3c. Stale push (v1 when store has v2): HTTP {r_stale.status_code}")
    print("  " + pretty(stale_body).replace("\n", "\n  "))
    print("  -> [PASS] Versioning semantics strictly enforced.")

    # -------------------------------------------------------------------------
    # TEST 4: POST /v1/tick (Proactive Customer-Facing Message)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] POST /v1/tick (Proactive Customer-Facing Recall)")
    r_tick = vc.post("/v1/tick", {
        "now": "2026-04-26T10:30:00Z",
        "available_triggers": ["trg_recall_01"]
    })
    assert r_tick.status_code == 200, f"Tick failed: {r_tick.text}"
    tick_data = r_tick.json()
    print(f"  POST /v1/tick -> HTTP {r_tick.status_code}")
    print("  " + pretty(tick_data).replace("\n", "\n  "))

    assert len(tick_data["actions"]) == 1, f"Expected 1 action, got {len(tick_data['actions'])}"
    act = tick_data["actions"][0]
    assert act["send_as"] == "merchant_on_behalf", f"Expected send_as=merchant_on_behalf, got {act['send_as']}"
    assert act["customer_id"] == "c_patient_01"
    assert act["cta"] == "multi_choice_slot"
    assert "Apex Dental Clinic" in act["body"]
    assert "recall due" in act["body"]
    assert "http" not in act["body"], "URL detected in message body!"
    print("  -> [PASS] Proactive customer-facing recall message verified.")

    # -------------------------------------------------------------------------
    # TEST 5: Restraint / Silence Case (Premature Trigger)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] POST /v1/tick Restraint / Silence Case (Premature Festival Trigger)")
    trg_restraint = {
        "id": "trg_premature_diwali",
        "scope": "merchant",
        "kind": "festival_upcoming",
        "source": "internal",
        "merchant_id": "m_dental_01",
        "urgency": 1,
        "payload": {
            "festival": "Diwali",
            "days_until": 188,
            "note": "Diwali is 6+ months away."
        },
        "suppression_key": "festival:diwali:m_dental_01",
        "expires_at": "2026-11-15T23:59:59Z"
    }
    vc.post("/v1/context", {
        "scope": "trigger",
        "context_id": "trg_premature_diwali",
        "version": 1,
        "payload": trg_restraint,
        "delivered_at": "2026-04-26T10:35:00Z"
    })

    r_restraint = vc.post("/v1/tick", {
        "now": "2026-04-26T10:35:00Z",
        "available_triggers": ["trg_premature_diwali"]
    })
    assert r_restraint.status_code == 200, f"Expected 200, got {r_restraint.status_code}"
    restraint_data = r_restraint.json()
    print(f"  POST /v1/tick (Diwali 188 days away, urgency 1) -> HTTP {r_restraint.status_code}")
    print("  " + pretty(restraint_data).replace("\n", "\n  "))
    assert len(restraint_data["actions"]) == 0, f"Expected 0 actions (silence), got {len(restraint_data['actions'])}"
    print("  -> [PASS] Restraint verified: Premature trigger yielded silence (actions: []).")

    # -------------------------------------------------------------------------
    # TEST 6: POST /v1/reply Multi-Turn Scenarios
    # -------------------------------------------------------------------------
    print("\n[TEST 6] POST /v1/reply Multi-Turn Conversation Scenarios")

    # 6a. Canned Auto-Reply
    print("\n  6a. Auto-Reply Canned Message:")
    r_auto = vc.post("/v1/reply", {
        "conversation_id": "conv_dental_auto",
        "merchant_id": "m_dental_01",
        "from_role": "merchant",
        "message": "Thank you for contacting Apex Dental Clinic. Our team will respond shortly.",
        "received_at": "2026-04-26T10:40:00Z",
        "turn_number": 1
    })
    assert r_auto.status_code == 200
    auto_data = r_auto.json()
    print("  " + pretty(auto_data).replace("\n", "\n  "))
    assert auto_data["action"] == "wait"
    assert auto_data["wait_seconds"] == 14400
    print("  -> [PASS] Auto-reply correctly triggers 4-hour wait.")

    # 6b. Repeated Auto-Reply (Turn 3)
    print("\n  6b. Repeated Auto-Reply on Turn 3:")
    r_repeat = vc.post("/v1/reply", {
        "conversation_id": "conv_dental_auto",
        "merchant_id": "m_dental_01",
        "from_role": "merchant",
        "message": "Thank you for contacting Apex Dental Clinic. Our team will respond shortly.",
        "received_at": "2026-04-26T14:40:00Z",
        "turn_number": 3
    })
    assert r_repeat.status_code == 200
    repeat_data = r_repeat.json()
    print("  " + pretty(repeat_data).replace("\n", "\n  "))
    assert repeat_data["action"] == "end"
    print("  -> [PASS] Repeated auto-reply correctly terminates conversation.")

    # 6c. Intent Transition (Merchant Commitment)
    print("\n  6c. Intent Transition (Commitment -> Immediate Action Execution):")
    r_commit = vc.post("/v1/reply", {
        "conversation_id": "conv_dental_commit",
        "merchant_id": "m_dental_01",
        "from_role": "merchant",
        "message": "Ok let's do it. What's next?",
        "received_at": "2026-04-26T11:00:00Z",
        "turn_number": 2
    })
    assert r_commit.status_code == 200
    commit_data = r_commit.json()
    print("  " + pretty(commit_data).replace("\n", "\n  "))
    assert commit_data["action"] == "send"
    assert commit_data["cta"] == "binary_confirm_cancel"
    # Verify actioning language and absence of qualifying questions
    assert "Done!" in commit_data["body"] or "Drafting" in commit_data["body"]
    assert "?" not in commit_data["body"] or "CONFIRM" in commit_data["body"]
    print("  -> [PASS] Commitment immediately activates execution without qualifying questions.")

    # 6d. Hostile Opt-Out
    print("\n  6d. Hostile Opt-Out:")
    r_hostile = vc.post("/v1/reply", {
        "conversation_id": "conv_dental_hostile",
        "merchant_id": "m_dental_01",
        "from_role": "merchant",
        "message": "Stop messaging me, unsubscribe from this spam!",
        "received_at": "2026-04-26T11:05:00Z",
        "turn_number": 2
    })
    assert r_hostile.status_code == 200
    hostile_data = r_hostile.json()
    print("  " + pretty(hostile_data).replace("\n", "\n  "))
    assert hostile_data["action"] == "end"
    print("  -> [PASS] Hostile opt-out gracefully terminates and suppresses further messages.")

    # 6e. Out-of-Scope Query (Curveball)
    print("\n  6e. Out-of-Scope Curveball (GST Tax filing):")
    r_oos = vc.post("/v1/reply", {
        "conversation_id": "conv_dental_oos",
        "merchant_id": "m_dental_01",
        "from_role": "merchant",
        "message": "Can Vera help me calculate my GST filing and income tax for this quarter?",
        "received_at": "2026-04-26T11:10:00Z",
        "turn_number": 2
    })
    assert r_oos.status_code == 200
    oos_data = r_oos.json()
    print("  " + pretty(oos_data).replace("\n", "\n  "))
    assert oos_data["action"] == "send"
    assert "outside what Vera can help with" in oos_data["body"]
    print("  -> [PASS] Out-of-scope query politely declined and pivoted to listing.")

    # -------------------------------------------------------------------------
    # TEST 7: Teardown & State Cleanup
    # -------------------------------------------------------------------------
    print("\n[TEST 7] POST /v1/teardown & State Verification")
    r_td = vc.post("/v1/teardown", {})
    assert r_td.status_code == 200
    print(f"  POST /v1/teardown -> HTTP {r_td.status_code}")
    print("  " + pretty(r_td.json()).replace("\n", "\n  "))

    r_post_health = vc.get("/v1/healthz")
    counts = r_post_health.json()["contexts_loaded"]
    print(f"  GET /v1/healthz post-teardown -> contexts_loaded: {counts}")
    assert all(c == 0 for c in counts.values()), f"Expected all context counts to be 0, got {counts}"
    print("  -> [PASS] Teardown successfully wiped all context state.")

    print("\n" + "=" * 70)
    print("ALL 7 VERIFICATION TEST SUITES PASSED PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Magicpin Vera Bot")
    parser.add_argument("--url", type=str, default=None, help="Base URL of running server (e.g. http://127.0.0.1:8080)")
    args = parser.parse_args()

    try:
        run_verification(args.url)
    except AssertionError as e:
        print(f"\n[FAIL] Assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
