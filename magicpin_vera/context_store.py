"""
Thread-safe versioned in-memory context store with exact challenge semantics.
Enforces idempotency, atomic replacement, and 409 conflict on stale versions.
"""

from __future__ import annotations
import threading
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Any


class ContextStore:
    def __init__(self):
        self._lock = threading.RLock()
        # Key: (scope, context_id) -> {"version": int, "payload": dict, "stored_at": str}
        self._contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # Suppression keys: key -> expires_at_iso
        self._suppressed: Dict[str, str] = {}
        # Sent messages history: conversation_id -> [turns]
        self._conversations: Dict[str, list] = {}

    def push(self, scope: str, context_id: str, version: int, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], int]:
        """
        Push context with strict versioning semantics.
        Returns: (success: bool, response_dict: dict, status_code: int)
        """
        valid_scopes = {"category", "merchant", "customer", "trigger"}
        if scope not in valid_scopes:
            return False, {"accepted": False, "reason": "invalid_scope", "details": f"Scope must be one of {valid_scopes}"}, 400

        with self._lock:
            key = (scope, context_id)
            current = self._contexts.get(key)

            if current is not None:
                current_version = current["version"]
                if version < current_version:
                    return False, {
                        "accepted": False,
                        "reason": "stale_version",
                        "current_version": current_version
                    }, 409
                elif version == current_version:
                    # Idempotent re-post: same version is a no-op
                    return True, {
                        "accepted": True,
                        "ack_id": f"ack_{context_id}_v{version}",
                        "stored_at": current["stored_at"]
                    }, 200

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self._contexts[key] = {
                "version": version,
                "payload": payload,
                "stored_at": now_iso
            }

            return True, {
                "accepted": True,
                "ack_id": f"ack_{context_id}_v{version}",
                "stored_at": now_iso
            }, 200

    def get(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._contexts.get((scope, context_id))
            return item["payload"] if item else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        with self._lock:
            item = self._contexts.get((scope, context_id))
            return item["version"] if item else None

    def get_category(self, slug: str) -> Optional[Dict[str, Any]]:
        return self.get("category", slug)

    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        return self.get("merchant", merchant_id)

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return self.get("customer", customer_id)

    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        return self.get("trigger", trigger_id)

    def get_counts(self) -> Dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for (scope, _), _ in self._contexts.items():
                if scope in counts:
                    counts[scope] += 1
        return counts

    def record_suppression(self, key: str, expires_at: Optional[str] = None):
        if not key:
            return
        with self._lock:
            self._suppressed[key] = expires_at or "2099-12-31T23:59:59Z"

    def is_suppressed(self, key: str, now_iso: Optional[str] = None) -> bool:
        if not key:
            return False
        with self._lock:
            expires_at = self._suppressed.get(key)
            if not expires_at:
                return False
            if now_iso and now_iso > expires_at:
                del self._suppressed[key]
                return False
            return True

    def get_conversation(self, conversation_id: str) -> list:
        with self._lock:
            return list(self._conversations.get(conversation_id, []))

    def append_conversation(self, conversation_id: str, turn: Dict[str, Any]):
        with self._lock:
            self._conversations.setdefault(conversation_id, []).append(turn)

    def wipe_state(self):
        """Reset state during test cleanup (POST /v1/teardown)."""
        with self._lock:
            self._contexts.clear()
            self._suppressed.clear()
            self._conversations.clear()


# Global singleton instance
store = ContextStore()
