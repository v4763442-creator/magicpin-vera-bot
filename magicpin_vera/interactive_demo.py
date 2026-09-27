"""
magicpin_vera/interactive_demo.py
Interactive CLI Playground for Magicpin Vera AI Engine.

Run this to interactively test and see results:
  python magicpin_vera/interactive_demo.py
"""

from __future__ import annotations
import sys
import os
import textwrap
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
from magicpin_vera.context_store import store
from magicpin_vera.conversation_handlers import ConversationHandler
from magicpin_vera.signal_extractor import (
    NormalizedCategory, NormalizedMerchant, NormalizedTrigger, NormalizedCustomer
)
from magicpin_vera.decision_engine import DecisionEngine
from magicpin_vera.message_composer import MessageComposer


# Sample realistic categories and merchants
DENTAL_CATEGORY = {
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
        {"id": "cat_off_1", "title": "Comprehensive Checkup + Scaling @ Rs.699", "audience": "all"}
    ]
}

RESTAURANT_CATEGORY = {
    "slug": "restaurants",
    "display_name": "Restaurants & Cafes",
    "voice": {
        "tone": "warm",
        "register": "collegial",
        "code_mix": "hindi_english_natural",
        "vocab_allowed": ["dining", "fresh", "special", "cover", "delivery"],
        "vocab_taboo": ["best price", "cheapest in town"]
    },
    "offer_catalog": [
        {"id": "cat_off_2", "title": "Corporate Lunch Thali @ Rs.115", "audience": "all"}
    ]
}

MERCHANT_ARUN = {
    "merchant_id": "m_arun_01",
    "category_slug": "dentists",
    "identity": {
        "name": "Apex Dental Care",
        "city": "Bengaluru",
        "locality": "Indiranagar",
        "owner_first_name": "Arun",
        "languages": ["en", "hi-en mix"]
    },
    "subscription": {"status": "active", "plan": "Pro", "days_remaining": 60},
    "performance": {"views": 520, "calls": 38, "directions": 22},
    "offers": [
        {"id": "off_arun_1", "title": "Comprehensive Checkup + Scaling @ Rs.699", "status": "active"}
    ]
}

CUSTOMER_SUNITA = {
    "customer_id": "c_sunita_01",
    "merchant_id": "m_arun_01",
    "identity": {"name": "Sunita Sharma", "language_pref": "hi-en mix"},
    "relationship": {
        "first_visit": "2025-04-10",
        "last_visit": "2025-10-15",
        "visits_total": 3,
        "services_received": ["scaling", "filling"]
    },
    "state": "lapsed_soft",
    "preferences": {"channel": "whatsapp", "reminder_opt_in": True},
    "consent": {"scope": ["reminders", "promotional_offers"]}
}


def print_boxed(text: str):
    print("+" + "-" * 67 + "+")
    for block in text.split("\n"):
        if not block.strip():
            print("| " + " " * 65 + " |")
            continue
        for line in textwrap.wrap(block, width=65):
            print(f"| {line.ljust(65)} |")
    print("+" + "-" * 67 + "+")


def demo_trigger(title: str, cat: dict, mer: dict, trg: dict, cus: dict | None = None):
    print("\n" + "=" * 67)
    print(f"SCENARIO: {title}")
    print("=" * 67)
    print(f"- Category: {cat['display_name']} ({cat['slug']})")
    print(f"- Merchant: {mer['identity']['name']} (Owner: {mer['identity'].get('owner_first_name', 'N/A')})")
    if cus:
        print(f"- Customer: {cus['identity']['name']} (Pref: {cus['identity']['language_pref']})")
    print(f"- Trigger:  {trg['kind']} (Urgency: {trg['urgency']})")
    print("-" * 67)

    norm_cat = NormalizedCategory(cat)
    norm_mer = NormalizedMerchant(mer)
    norm_trg = NormalizedTrigger(trg)
    norm_cus = NormalizedCustomer(cus)

    candidate = DecisionEngine.evaluate_trigger(norm_cat, norm_mer, norm_trg, norm_cus)
    if not candidate:
        print("[DECISION ENGINE RESTRAINT]")
        print("Outcome: SILENCE (No message sent).")
        print("Why: Decision engine determined outreach is premature or low-urgency. Restraint is the winning decision.")
        input("\nPress Enter to return to menu...")
        return

    composed = MessageComposer.compose_from_normalized(norm_cat, norm_mer, norm_trg, norm_cus, candidate)
    
    print("[COMPOSED OUTBOUND MESSAGE]")
    print(f"Send As:          {composed['send_as']}")
    print(f"CTA Format:       {composed['cta']}")
    print(f"Suppression Key:  {composed['suppression_key']}")
    print(f"Rationale:        {composed['rationale']}")
    print("\n[MESSAGE BODY (WHATSAPP PREVIEW)]:")
    print_boxed(composed['body'])

    # Record outbound message in store for multi-turn continuity
    conv_id = f"demo_conv_{mer['merchant_id']}_{trg['id']}"
    store.append_conversation(conv_id, {
        "from": "vera",
        "message": composed['body'],
        "turn": 1,
        "template_name": composed.get("template_name")
    })

    # Allow the user to immediately reply to Vera's question!
    owner = mer['identity'].get('owner_first_name', 'Merchant')
    print(f"\n[INTERACTIVE TURN -- REPLY AS {owner.upper()}]")
    print("Vera just asked you the question in the message above.")
    print("Type your reply (e.g. 'YES', 'Ok let's do it', or your question) or press Enter to return to menu:")

    turn = 2
    while True:
        try:
            reply_text = input(f"\n[{owner}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not reply_text:
            break

        resp = ConversationHandler.handle_reply(
            conversation_id=conv_id,
            merchant_id=mer['merchant_id'],
            customer_id=cus.get("customer_id") if cus else None,
            from_role="merchant",
            message=reply_text,
            turn_number=turn
        )

        action = resp["action"]
        print(f"\n[Vera Action: {action.upper()}]")
        print(f"Rationale: {resp['rationale']}")
        if action == "send":
            print(f"CTA:       {resp.get('cta')}")
            print("\n[VERA'S RESPONSE]:")
            print_boxed(resp.get('body', ''))
        elif action == "wait":
            print(f"Vera Status: Paused for {resp.get('wait_seconds')} seconds waiting for human owner.")
        elif action == "end":
            print("Vera Status: Conversation gracefully ended.")
            break

        turn += 1
        print("\n(Type next reply to continue conversation, or press Enter to return to menu)")


def interactive_chat():
    print("\n" + "=" * 67)
    print("INTERACTIVE CHAT WITH VERA")
    print("You are Dr. Arun (Owner of Apex Dental Care).")
    print("Type any message to Vera (or type 'exit' to return to menu).")
    print("Try asking things like:")
    print("  * 'Ok let\'s do it. What\'s next?'           (Tests intent transition)")
    print("  * 'Thank you, our team will get back to you' (Tests auto-reply detection)")
    print("  * 'Stop messaging me, unsubscribe'           (Tests hostile opt-out)")
    print("  * 'Can you help me file my GST tax return?'  (Tests out-of-scope curveball)")
    print("  * 'How does this work?'                      (Tests explanatory guidance)")
    print("=" * 67)

    conv_id = "demo_interactive_conv"
    turn = 1

    while True:
        try:
            user_msg = input(f"\n[Turn {turn}] You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat.")
            break

        if not user_msg or user_msg.lower() in ("exit", "quit", "q"):
            break

        resp = ConversationHandler.handle_reply(
            conversation_id=conv_id,
            merchant_id="m_arun_01",
            customer_id=None,
            from_role="merchant",
            message=user_msg,
            turn_number=turn
        )

        action = resp["action"]
        print(f"\n[Vera Action: {action.upper()}]")
        print(f"Rationale: {resp['rationale']}")
        if action == "send":
            print(f"CTA:       {resp.get('cta')}")
            print("\n[VERA'S RESPONSE]:")
            print_boxed(resp.get('body', ''))
        elif action == "wait":
            print(f"Vera Status: Paused for {resp.get('wait_seconds')} seconds waiting for human owner.")
        elif action == "end":
            print("Vera Status: Conversation gracefully ended and suppressed.")
            break

        turn += 1


def main():
    while True:
        print("\n" + "=" * 67)
        print("MAGICPIN VERA -- HANDS-ON DEMO MENU")
        print("=" * 67)
        print("1. Scenario A: Customer Recall Due (Sunita Sharma - Dental Cleaning)")
        print("2. Scenario B: Active Planning Intent (Corporate Thali Package Draft)")
        print("3. Scenario C: Restraint Test (Diwali Festival 188 Days Away - Silence)")
        print("4. Scenario D: Urgent Regulatory Compliance Advisory (DCI Radiograph)")
        print("5. Scenario E: IPL Match Night Strategy (Restaurant Dine-in vs Delivery)")
        print("6. Scenario F: Interactive Live Chat (Talk to Vera yourself)")
        print("7. Run Full Automated Verification Suite (verify_bot.py)")
        print("0. Exit")
        print("=" * 67)

        try:
            choice = input("Enter choice (0-7): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if choice.lower() in ("yes", "y", "ok"):
            print("\n[Tip] You entered 'YES' at the main menu!")
            print("To see Vera draft the Corporate Thali WhatsApp note:")
            print("  1. Press 2 on this menu")
            print("  2. When prompted '[Suresh]:', type 'YES' or 'Ok let's do it!'")
            continue

        if choice == "1":
            trg = {
                "id": "trg_recall_sunita",
                "scope": "customer",
                "kind": "recall_due",
                "urgency": 4,
                "merchant_id": "m_arun_01",
                "customer_id": "c_sunita_01",
                "payload": {
                    "service_due": "6-month dental checkup & cleaning",
                    "available_slots": [
                        {"label": "Saturday 10:30am", "iso": "2026-05-02T10:30:00Z"},
                        {"label": "Sunday 11:00am", "iso": "2026-05-03T11:00:00Z"}
                    ]
                }
            }
            demo_trigger("Patient Recall Due", DENTAL_CATEGORY, MERCHANT_ARUN, trg, CUSTOMER_SUNITA)

        elif choice == "2":
            trg = {
                "id": "trg_thali_plan",
                "scope": "merchant",
                "kind": "active_planning_intent",
                "urgency": 5,
                "merchant_id": "m_rest_01",
                "payload": {
                    "intent_topic": "corporate thali package",
                    "merchant_last_message": "Can you prepare a plan for corporate lunches?"
                }
            }
            mer_rest = {
                "merchant_id": "m_rest_01",
                "category_slug": "restaurants",
                "identity": {"name": "Flavors of Punjab", "locality": "Koramangala", "owner_first_name": "Suresh"},
                "subscription": {"status": "active"},
                "performance": {"views": 1200, "calls": 80},
                "offers": []
            }
            demo_trigger("Active Planning Fulfillment", RESTAURANT_CATEGORY, mer_rest, trg)

        elif choice == "3":
            trg = {
                "id": "trg_premature_diwali",
                "scope": "merchant",
                "kind": "festival_upcoming",
                "urgency": 1,
                "merchant_id": "m_arun_01",
                "payload": {"festival": "Diwali", "days_until": 188}
            }
            demo_trigger("Decision Restraint (Diwali 6 months away)", DENTAL_CATEGORY, MERCHANT_ARUN, trg)

        elif choice == "4":
            trg = {
                "id": "trg_dci_radiograph",
                "scope": "merchant",
                "kind": "regulation_change",
                "urgency": 5,
                "merchant_id": "m_arun_01",
                "payload": {
                    "deadline_iso": "2026-12-15",
                    "top_item_id": "cde_rvg_01"
                }
            }
            demo_trigger("Regulatory Compliance Alert", DENTAL_CATEGORY, MERCHANT_ARUN, trg)

        elif choice == "5":
            trg = {
                "id": "trg_ipl_match",
                "scope": "merchant",
                "kind": "ipl_match_today",
                "urgency": 4,
                "merchant_id": "m_rest_01",
                "payload": {
                    "match": "RCB vs CSK",
                    "match_time_iso": "2026-05-02T19:30:00Z"
                }
            }
            mer_rest = {
                "merchant_id": "m_rest_01",
                "category_slug": "restaurants",
                "identity": {"name": "Tandoor Nights", "locality": "Indiranagar", "owner_first_name": "Karthik"},
                "subscription": {"status": "active"},
                "performance": {"views": 1500, "calls": 95},
                "offers": [{"id": "off_combo", "title": "IPL Match Combo Meal", "status": "active"}]
            }
            demo_trigger("IPL Match Night Strategy", RESTAURANT_CATEGORY, mer_rest, trg)

        elif choice == "6":
            interactive_chat()

        elif choice == "7":
            import subprocess
            subprocess.run([sys.executable, str(Path(workspace_root) / "magicpin_vera" / "verify_bot.py")])

        elif choice == "0":
            print("Exiting playground. Have fun!")
            break
        else:
            print("Invalid selection, please try again.")


if __name__ == "__main__":
    main()
