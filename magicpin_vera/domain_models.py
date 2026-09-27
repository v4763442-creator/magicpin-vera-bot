"""
Domain models and schema definitions for Magicpin Vera AI Engine.
Strictly conforms to the 4-context framework and HTTP API specifications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# 1. CATEGORY CONTEXT MODELS
# =============================================================================

@dataclass
class VoiceProfile:
    tone: str = "professional"
    register: str = "collegial"
    code_mix: str = "hindi_english_natural"
    vocab_allowed: List[str] = field(default_factory=list)
    vocab_taboo: List[str] = field(default_factory=list)
    salutation_examples: List[str] = field(default_factory=list)
    tone_examples: List[str] = field(default_factory=list)


@dataclass
class CategoryOffer:
    id: str = ""
    title: str = ""
    value: str = ""
    audience: str = "all"
    type: str = "service_at_price"


@dataclass
class PeerStats:
    scope: str = ""
    avg_rating: float = 0.0
    avg_review_count: int = 0
    avg_views_30d: int = 0
    avg_calls_30d: int = 0
    avg_directions_30d: int = 0
    avg_ctr: float = 0.0
    avg_photos: int = 0
    avg_post_freq_days: int = 14
    retention_6mo_pct: float = 0.0


@dataclass
class DigestItem:
    id: str = ""
    kind: str = "research"  # research | compliance | cde | trend | tech
    title: str = ""
    source: str = ""
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    summary: str = ""
    actionable: str = ""
    date: Optional[str] = None
    credits: Optional[int] = None


@dataclass
class PatientContentItem:
    id: str = ""
    title: str = ""
    channel: str = "whatsapp"
    length_seconds: int = 60
    body: str = ""


@dataclass
class SeasonalBeat:
    month_range: str = ""
    note: str = ""


@dataclass
class TrendSignal:
    query: str = ""
    delta_yoy: float = 0.0
    segment_age: str = ""
    skew: str = ""


@dataclass
class CategoryContext:
    slug: str = ""
    display_name: str = ""
    voice: VoiceProfile = field(default_factory=VoiceProfile)
    offer_catalog: List[CategoryOffer] = field(default_factory=list)
    peer_stats: PeerStats = field(default_factory=PeerStats)
    digest: List[DigestItem] = field(default_factory=list)
    patient_content_library: List[PatientContentItem] = field(default_factory=list)
    seasonal_beats: List[SeasonalBeat] = field(default_factory=list)
    trend_signals: List[TrendSignal] = field(default_factory=list)
    regulatory_authorities: List[str] = field(default_factory=list)
    professional_journals: List[str] = field(default_factory=list)


# =============================================================================
# 2. MERCHANT CONTEXT MODELS
# =============================================================================

@dataclass
class MerchantIdentity:
    name: str = ""
    city: str = ""
    locality: str = ""
    place_id: str = ""
    verified: bool = False
    languages: List[str] = field(default_factory=lambda: ["en"])
    owner_first_name: str = ""
    established_year: Optional[int] = None


@dataclass
class MerchantSubscription:
    status: str = "active"  # active | expired | trial
    plan: str = "Pro"
    days_remaining: int = 0
    days_since_expiry: Optional[int] = None
    renewed_at: Optional[str] = None


@dataclass
class PerformanceDelta:
    views_pct: float = 0.0
    calls_pct: float = 0.0
    ctr_pct: float = 0.0


@dataclass
class PerformanceSnapshot:
    window_days: int = 30
    views: int = 0
    calls: int = 0
    directions: int = 0
    ctr: float = 0.0
    leads: int = 0
    delta_7d: PerformanceDelta = field(default_factory=PerformanceDelta)


@dataclass
class MerchantOffer:
    id: str = ""
    title: str = ""
    status: str = "active"  # active | expired | paused
    started: Optional[str] = None
    ended: Optional[str] = None


@dataclass
class CustomerAggregate:
    total_unique_ytd: int = 0
    lapsed_180d_plus: int = 0
    retention_6mo_pct: float = 0.0
    high_risk_adult_count: int = 0


@dataclass
class ConversationTurn:
    ts: str = ""
    from_role: str = ""  # vera | merchant | customer
    body: str = ""
    engagement: str = ""


@dataclass
class ReviewTheme:
    theme: str = ""
    sentiment: str = "neutral"
    occurrences_30d: int = 0
    trend: str = "flat"
    common_quote: str = ""


@dataclass
class MerchantContext:
    merchant_id: str = ""
    category_slug: str = ""
    identity: MerchantIdentity = field(default_factory=MerchantIdentity)
    subscription: MerchantSubscription = field(default_factory=MerchantSubscription)
    performance: PerformanceSnapshot = field(default_factory=PerformanceSnapshot)
    offers: List[MerchantOffer] = field(default_factory=list)
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    customer_aggregate: CustomerAggregate = field(default_factory=CustomerAggregate)
    signals: List[str] = field(default_factory=list)
    review_themes: List[ReviewTheme] = field(default_factory=list)


# =============================================================================
# 3. TRIGGER CONTEXT MODELS
# =============================================================================

@dataclass
class TriggerContext:
    id: str = ""
    scope: Literal["merchant", "customer"] = "merchant"
    kind: str = ""
    source: Literal["external", "internal"] = "internal"
    merchant_id: str = ""
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    urgency: int = 1  # 1 to 5
    suppression_key: str = ""
    expires_at: str = ""


# =============================================================================
# 4. CUSTOMER CONTEXT MODELS
# =============================================================================

@dataclass
class CustomerIdentity:
    name: str = ""
    phone_redacted: str = "<phone>"
    language_pref: str = "en"  # en | hi-en mix | hi
    age_band: Optional[str] = None


@dataclass
class CustomerRelationship:
    first_visit: str = ""
    last_visit: str = ""
    visits_total: int = 0
    services_received: List[str] = field(default_factory=list)
    lifetime_value: int = 0


@dataclass
class CustomerPreferences:
    channel: str = "whatsapp"
    preferred_slots: Optional[str] = None
    reminder_opt_in: bool = True


@dataclass
class CustomerConsent:
    opted_in_at: str = ""
    scope: List[str] = field(default_factory=list)


@dataclass
class CustomerContext:
    customer_id: str = ""
    merchant_id: str = ""
    identity: CustomerIdentity = field(default_factory=CustomerIdentity)
    relationship: CustomerRelationship = field(default_factory=CustomerRelationship)
    state: Literal["new", "active", "lapsed_soft", "lapsed_hard", "churned"] = "active"
    preferences: CustomerPreferences = field(default_factory=CustomerPreferences)
    consent: CustomerConsent = field(default_factory=CustomerConsent)


# =============================================================================
# 5. COMPOSITION & API RESPONSE MODELS
# =============================================================================

CtaType = Literal["binary_yes_no", "open_ended", "multi_choice_slot", "binary_confirm_cancel", "none"]
SendAsType = Literal["vera", "merchant_on_behalf"]


@dataclass
class ComposedMessage:
    body: str
    cta: CtaType
    send_as: SendAsType
    suppression_key: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "body": self.body,
            "cta": self.cta,
            "send_as": self.send_as,
            "suppression_key": self.suppression_key,
            "rationale": self.rationale,
        }


# =============================================================================
# 6. PYDANTIC HTTP CONTRACT MODELS
# =============================================================================

class ContextPushRequest(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str


class ContextPushSuccess(BaseModel):
    accepted: bool = True
    ack_id: str
    stored_at: str


class ContextPushConflict(BaseModel):
    accepted: bool = False
    reason: str = "stale_version"
    current_version: int


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class TickActionItem(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: SendAsType
    trigger_id: str
    template_name: str
    template_params: List[str]
    body: str
    cta: CtaType
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[TickActionItem] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str
    received_at: str
    turn_number: int


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[CtaType] = None
    wait_seconds: Optional[int] = None
    rationale: str


class HealthzResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int
    contexts_loaded: Dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str = "vivek_ai"
    team_members: List[str] = Field(default_factory=lambda: ["Vivek"])
    model: str = "vera-grounded-deterministic-v2"
    approach: str = "Context-grounded 8-stage decision & composition engine with dynamic voice alignment"
    contact_email: str = "vivek_23cs465@dtu.ac.in"
    version: str = "2.0.0"
    submitted_at: str = "2026-04-26T08:00:00Z"
