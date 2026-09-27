"""
Signal extraction and dynamic context normalization.
Parses Category, Merchant, Trigger, and Customer contexts without static assumptions.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List


class NormalizedCategory:
    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.slug: str = data.get("slug", "")
        self.display_name: str = data.get("display_name", self.slug.capitalize())
        
        voice_dict = data.get("voice", {})
        self.tone: str = voice_dict.get("tone", "professional")
        self.register: str = voice_dict.get("register", "collegial")
        self.code_mix: str = voice_dict.get("code_mix", "hindi_english_natural")
        self.vocab_allowed: List[str] = voice_dict.get("vocab_allowed", [])
        self.vocab_taboo: List[str] = voice_dict.get("vocab_taboo", [])
        self.salutation_examples: List[str] = voice_dict.get("salutation_examples", [])
        self.tone_examples: List[str] = voice_dict.get("tone_examples", [])

        self.offer_catalog: List[Dict[str, Any]] = data.get("offer_catalog", [])
        self.peer_stats: Dict[str, Any] = data.get("peer_stats", {})
        self.digest: List[Dict[str, Any]] = data.get("digest", [])
        self.patient_content_library: List[Dict[str, Any]] = data.get("patient_content_library", [])
        self.seasonal_beats: List[Dict[str, Any]] = data.get("seasonal_beats", [])
        self.trend_signals: List[Dict[str, Any]] = data.get("trend_signals", [])

    def find_digest_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        for d in self.digest:
            if d.get("id") == item_id:
                return d
        return None


class NormalizedMerchant:
    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.merchant_id: str = data.get("merchant_id", "")
        self.category_slug: str = data.get("category_slug", "")

        identity = data.get("identity", {})
        self.name: str = identity.get("name", "Merchant")
        self.city: str = identity.get("city", "")
        self.locality: str = identity.get("locality", "")
        self.place_id: str = identity.get("place_id", "")
        self.verified: bool = identity.get("verified", False)
        self.languages: List[str] = identity.get("languages", ["en"])
        self.owner_first_name: str = identity.get("owner_first_name", "")
        self.established_year: Optional[int] = identity.get("established_year")

        sub = data.get("subscription", {})
        self.subscription_status: str = sub.get("status", "active")
        self.subscription_plan: str = sub.get("plan", "Pro")
        self.days_remaining: int = sub.get("days_remaining", 0)
        self.days_since_expiry: Optional[int] = sub.get("days_since_expiry")

        perf = data.get("performance", {})
        self.views_30d: int = perf.get("views", 0)
        self.calls_30d: int = perf.get("calls", 0)
        self.directions_30d: int = perf.get("directions", 0)
        self.ctr: float = perf.get("ctr", 0.0)
        self.leads_30d: int = perf.get("leads", 0)
        
        delta = perf.get("delta_7d", {})
        self.delta_views_pct: float = delta.get("views_pct", 0.0)
        self.delta_calls_pct: float = delta.get("calls_pct", 0.0)
        self.delta_ctr_pct: float = delta.get("ctr_pct", 0.0)

        # Separate active and expired offers
        raw_offers = data.get("offers", [])
        self.active_offers: List[Dict[str, Any]] = [o for o in raw_offers if o.get("status") == "active"]
        self.expired_offers: List[Dict[str, Any]] = [o for o in raw_offers if o.get("status") == "expired"]

        cust_agg = data.get("customer_aggregate", {})
        self.total_unique_customers_ytd: int = cust_agg.get("total_unique_ytd", 0)
        self.lapsed_180d_plus: int = cust_agg.get("lapsed_180d_plus", 0)
        self.retention_6mo_pct: float = cust_agg.get("retention_6mo_pct", 0.0)
        self.high_risk_adult_count: int = cust_agg.get("high_risk_adult_count", 0)

        self.signals: List[str] = data.get("signals", [])
        self.review_themes: List[Dict[str, Any]] = data.get("review_themes", [])
        self.conversation_history: List[Dict[str, Any]] = data.get("conversation_history", [])

    def preferred_name(self) -> str:
        """Return owner first name if present, else business name."""
        if self.owner_first_name:
            if self.category_slug == "dentists" and not self.owner_first_name.lower().startswith("dr"):
                return f"Dr. {self.owner_first_name}"
            return self.owner_first_name
        return self.name

    def prefers_hindi_mix(self) -> bool:
        return "hi" in self.languages or "hi-en mix" in self.languages


class NormalizedTrigger:
    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.id: str = data.get("id", "")
        self.scope: str = data.get("scope", "merchant")
        self.kind: str = data.get("kind", "")
        self.source: str = data.get("source", "internal")
        self.merchant_id: str = data.get("merchant_id", "")
        self.customer_id: Optional[str] = data.get("customer_id")
        self.payload: Dict[str, Any] = data.get("payload", {})
        self.urgency: int = data.get("urgency", 1)
        self.suppression_key: str = data.get("suppression_key", "")
        self.expires_at: str = data.get("expires_at", "")


class NormalizedCustomer:
    def __init__(self, data: Optional[Dict[str, Any]]):
        self.raw = data or {}
        if not data:
            self.exists = False
            self.customer_id = ""
            self.name = ""
            self.language_pref = "en"
            self.state = "active"
            self.preferred_slots = None
            self.services_received = []
            self.visits_total = 0
            self.days_since_last_visit = None
            return

        self.exists = True
        self.customer_id: str = data.get("customer_id", "")
        self.merchant_id: str = data.get("merchant_id", "")

        identity = data.get("identity", {})
        self.name: str = identity.get("name", "Customer")
        self.language_pref: str = identity.get("language_pref", "en")
        self.age_band: Optional[str] = identity.get("age_band")

        rel = data.get("relationship", {})
        self.first_visit: str = rel.get("first_visit", "")
        self.last_visit: str = rel.get("last_visit", "")
        self.visits_total: int = rel.get("visits_total", 0)
        self.services_received: List[str] = rel.get("services_received", [])
        self.lifetime_value: int = rel.get("lifetime_value", 0)

        self.state: str = data.get("state", "active")
        
        prefs = data.get("preferences", {})
        self.preferred_slots: Optional[str] = prefs.get("preferred_slots")
        self.reminder_opt_in: bool = prefs.get("reminder_opt_in", True)

        consent = data.get("consent", {})
        self.consent_scope: List[str] = consent.get("scope", [])

    def prefers_hindi_mix(self) -> bool:
        return self.language_pref in ("hi", "hi-en mix")
