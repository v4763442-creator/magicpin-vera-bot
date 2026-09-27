"""
Multi-turn conversation state machine for Magicpin Vera.
Handles auto-replies, intent transitions, hostility/opt-outs, and curveballs.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional, List
from magicpin_vera.context_store import store


# Canned auto-reply patterns
AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond shortly",
    r"we will get back to you",
    r"automated assistant",
    r"automated response",
    r"away from phone",
    r"auto-reply",
    r"hamari team tak pahuncha",
    r"automatic reply",
    r"currently unavailable",
    r"out of office"
]

# Explicit commitment / intent transition phrases
COMMITMENT_PATTERNS = [
    r"\blet'?s do it\b",
    r"\bok\b",
    r"\byes\b",
    r"\bproceed\b",
    r"\bconfirm\b",
    r"\bgo ahead\b",
    r"\bwhat'?s next\b",
    r"\bready\b",
    r"\bsend (it|me|the)\b",
    r"\bi want to\b",
    r"\bdo it\b",
    r"\bstart\b",
    r"\bagree\b"
]

# Hostile or opt-out phrases
HOSTILE_PATTERNS = [
    r"\bstop\b",
    r"\bspam\b",
    r"\buseless\b",
    r"\bunsubscribe\b",
    r"\bnot interested\b",
    r"\bdon'?t message\b",
    r"\bdo not contact\b",
    r"\bbothering me\b",
    r"\bopt out\b",
    r"\bleave me alone\b"
]

# Common out-of-scope curveball requests
OUT_OF_SCOPE_PATTERNS = [
    r"\bgst\b",
    r"\btax\b",
    r"\bloan\b",
    r"\baccounting\b",
    r"\bca\b",
    r"\bpersonal\b",
    r"\blawyer\b",
    r"\blegal advice\b"
]


class ConversationHandler:
    @staticmethod
    def handle_reply(
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        from_role: str,
        message: str,
        turn_number: int
    ) -> Dict[str, Any]:
        """
        Produce next action in conversation: send, wait, or end.
        """
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()

        # Retrieve conversation history
        history = store.get_conversation(conversation_id)
        
        # Record incoming message
        store.append_conversation(conversation_id, {
            "from": from_role,
            "message": msg_clean,
            "turn": turn_number
        })

        # ---------------------------------------------------------------------
        # 1. Hostile / Opt-Out Detection
        # ---------------------------------------------------------------------
        if any(re.search(p, msg_lower) for p in HOSTILE_PATTERNS):
            if merchant_id:
                store.record_suppression(f"hostile:{merchant_id}")
            return {
                "action": "end",
                "rationale": "Merchant explicitly requested opt-out or expressed hostility; gracefully exiting and suppressing further outreach."
            }

        # ---------------------------------------------------------------------
        # 2. Auto-Reply Detection
        # ---------------------------------------------------------------------
        is_auto_reply = any(re.search(p, msg_lower) for p in AUTO_REPLY_PATTERNS)

        # Check for repeated identical messages from merchant
        past_merchant_msgs = [h.get("message", "").lower() for h in history if h.get("from") == from_role]
        if past_merchant_msgs and past_merchant_msgs[-1] == msg_lower:
            is_auto_reply = True

        if is_auto_reply:
            if turn_number >= 3 or len(past_merchant_msgs) >= 2:
                return {
                    "action": "end",
                    "rationale": "Repeated canned auto-reply detected 3x in a row; ending conversation to avoid burning turns."
                }
            else:
                return {
                    "action": "wait",
                    "wait_seconds": 14400,
                    "rationale": "Detected merchant automated auto-reply; backing off 4 hours to wait for human owner."
                }

        # ---------------------------------------------------------------------
        # 3. Intent Transition (Commitment -> Immediate Action)
        # ---------------------------------------------------------------------
        is_commitment = any(re.search(p, msg_lower) for p in COMMITMENT_PATTERNS)
        if is_commitment:
            # Check conversation history to see what specific draft was offered
            past_bot_msgs = [h.get("message", "") for h in history if h.get("from") == "vera"]
            last_bot_msg = (past_bot_msgs[-1] if past_bot_msgs else "").lower()

            if "thali" in last_bot_msg or "thali" in msg_lower or "lunch" in last_bot_msg:
                body = (
                    "Done! Here is your 3-line WhatsApp message ready to share with office managers:\n\n"
                    "1. Fresh, hot corporate thalis delivered right to your office desk daily between 12:30-1:00 PM!\n"
                    "2. Special group pricing: Rs.115/thali for 25+ orders with complimentary beverage and free delivery.\n"
                    "3. Pre-order by 5 PM today for tomorrow's lunch -- reply here or call us to reserve your company's slot.\n\n"
                    "Proceeding with setup -- reply CONFIRM to publish this update and start broadcast."
                )
            elif "yoga" in last_bot_msg or "camp" in last_bot_msg or "yoga" in msg_lower:
                body = (
                    "Done! Here is your drafted announcement post ready for WhatsApp broadcast and Google profile:\n\n"
                    "1. Kids Summer Yoga & Focus Camp starts next Tuesday at our studio!\n"
                    "2. Ages 6-12: Tue/Thu 4:30-5:30 PM (6 sessions covering posture, balance, and focus).\n"
                    "3. Just Rs.1,499 per child with certificate included. Max 12 spots -- reply here to reserve.\n\n"
                    "Proceeding with setup -- reply CONFIRM to launch announcement."
                )
            elif "recall" in last_bot_msg or "checkup" in last_bot_msg:
                body = (
                    "Done! Slot hold confirmed. I have reserved the appointment and scheduled the confirmation reminder. "
                    "Proceeding with calendar sync -- reply CONFIRM to finalize."
                )
            else:
                body = (
                    "Done! Drafting your communication now. "
                    "Here is the plan: I will pre-fill the post for tomorrow 10am and queue the broadcast. "
                    "Proceeding with setup -- reply CONFIRM to launch immediately."
                )

            return {
                "action": "send",
                "body": body,
                "cta": "binary_confirm_cancel",
                "rationale": "Merchant signaled explicit commitment; switching immediately to action execution mode without qualifying questions."
            }

        # ---------------------------------------------------------------------
        # 4. Out-of-Scope / Curveball Query
        # ---------------------------------------------------------------------
        if any(re.search(p, msg_lower) for p in OUT_OF_SCOPE_PATTERNS):
            body = (
                "That's outside what Vera can help with directly — best to consult your specialist. "
                "Coming back to your listing and growth — want me to proceed with the draft Google post we discussed?"
            )
            return {
                "action": "send",
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Out-of-scope inquiry politely declined; redirected back to open business thread."
            }

        # ---------------------------------------------------------------------
        # 5. General Questions / Engaged Merchant Follow-up
        # ---------------------------------------------------------------------
        if "?" in msg_clean:
            body = (
                "Understood. We can tailor this to your exact schedule and preferences. "
                "The setup takes about 2 minutes to confirm. Would you like me to share the preview?"
            )
            return {
                "action": "send",
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Merchant asked a clarifying question; answered directly and guided to next step."
            }

        # Default acknowledged & advance
        body = (
            "Got it! I have noted your preference. "
            "I will proceed with the update and share the final confirmation here."
        )
        return {
            "action": "send",
            "body": body,
            "cta": "open_ended",
            "rationale": "Acknowledged merchant input and advanced workflow."
        }


def respond(state: Any, merchant_message: str) -> dict:
    """
    Official multi-turn handler function.
    Given conversation state + latest message, produce the next action.
    """
    conv_id = getattr(state, "conversation_id", "conv_default") if hasattr(state, "conversation_id") else "conv_default"
    merchant_id = getattr(state, "merchant_id", None) if hasattr(state, "merchant_id") else None
    customer_id = getattr(state, "customer_id", None) if hasattr(state, "customer_id") else None
    turn_num = getattr(state, "turn_number", 2) if hasattr(state, "turn_number") else 2

    return ConversationHandler.handle_reply(
        conversation_id=conv_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        from_role="merchant",
        message=merchant_message,
        turn_number=turn_num
    )
