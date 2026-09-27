"""
Contextual decision engine: Decouples trigger detection from communication.
Evaluates trigger timing, merchant state, and category context to determine candidate actions or restraint.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple
from magicpin_vera.signal_extractor import (
    NormalizedCategory, NormalizedMerchant, NormalizedTrigger, NormalizedCustomer
)


class CandidateAction:
    def __init__(
        self,
        action_type: str,  # "send_message" | "silence" | "defer"
        priority: int,     # 1 (low) to 10 (urgent)
        strategy: str,     # name of the composition strategy
        rationale: str,
        context_data: Dict[str, Any]
    ):
        self.action_type = action_type
        self.priority = priority
        self.strategy = strategy
        self.rationale = rationale
        self.context_data = context_data


class DecisionEngine:
    @staticmethod
    def evaluate_trigger(
        category: NormalizedCategory,
        merchant: NormalizedMerchant,
        trigger: NormalizedTrigger,
        customer: NormalizedCustomer,
        now_iso: Optional[str] = None
    ) -> Optional[CandidateAction]:
        """
        Determine the next best action for a given trigger.
        Returns a CandidateAction or None if silence/restraint is the optimal decision.
        """
        # 1. Expiration check
        if trigger.expires_at and now_iso and now_iso > trigger.expires_at:
            return None  # Trigger is stale

        # 2. Customer consent check for customer-scoped triggers
        if trigger.scope == "customer" and customer.exists:
            if not customer.reminder_opt_in and "promotional_offers" not in customer.consent_scope:
                # Customer has explicitly opted out of outreach
                return None

        kind = trigger.kind
        payload = trigger.payload

        # -------------------------------------------------------------------------
        # Scenario A: Active Planning Intent (Highest Priority)
        # -------------------------------------------------------------------------
        if kind == "active_planning_intent":
            topic = payload.get("intent_topic", "")
            return CandidateAction(
                action_type="send_message",
                priority=10,
                strategy="active_planning_fulfillment",
                rationale=f"Fulfilling merchant's explicit planning intent for '{topic}' with a concrete draft.",
                context_data={"topic": topic, "merchant_msg": payload.get("merchant_last_message", "")}
            )

        # -------------------------------------------------------------------------
        # Scenario B: Customer Appointments & Recalls (Customer-Facing)
        # -------------------------------------------------------------------------
        if kind == "appointment_tomorrow":
            return CandidateAction(
                action_type="send_message",
                priority=9,
                strategy="appointment_reminder",
                rationale="Sending timely appointment confirmation to reduce no-shows.",
                context_data=payload
            )

        if kind == "recall_due":
            return CandidateAction(
                action_type="send_message",
                priority=8,
                strategy="customer_recall",
                rationale="Timed recall reminder aligned with customer visit interval and slot preferences.",
                context_data=payload
            )

        if kind == "chronic_refill_due":
            return CandidateAction(
                action_type="send_message",
                priority=9,
                strategy="chronic_refill",
                rationale="Proactive medication refill alert before chronic patient runs out of stock.",
                context_data=payload
            )

        if kind in ("customer_lapsed_soft", "customer_lapsed_hard"):
            days = payload.get("days_since_last_visit", payload.get("days_since_expiry", 60))
            return CandidateAction(
                action_type="send_message",
                priority=7,
                strategy="customer_winback",
                rationale=f"Low-friction winback proposal for lapsed customer ({days} days inactive).",
                context_data=payload
            )

        if kind in ("wedding_package_followup", "trial_followup"):
            return CandidateAction(
                action_type="send_message",
                priority=8,
                strategy="service_stage_followup",
                rationale="Follow-up on service trial or wedding timeline window.",
                context_data=payload
            )

        # -------------------------------------------------------------------------
        # Scenario C: Critical Regulatory, Safety, & Compliance Alerts
        # -------------------------------------------------------------------------
        if kind in ("regulation_change", "supply_alert"):
            return CandidateAction(
                action_type="send_message",
                priority=9,
                strategy="compliance_alert",
                rationale="Regulatory compliance or product alert with specific batch/dosage parameters.",
                context_data=payload
            )

        # -------------------------------------------------------------------------
        # Scenario D: Performance Dips & Seasonal Reframing
        # -------------------------------------------------------------------------
        if kind in ("perf_dip", "seasonal_perf_dip"):
            is_seasonal = payload.get("is_expected_seasonal", False)
            metric = payload.get("metric", "calls")
            delta_pct = payload.get("delta_pct", 0.0)

            # If expected seasonal drop (e.g. gym April lull), reframe and avoid panic discount
            if is_seasonal:
                return CandidateAction(
                    action_type="send_message",
                    priority=6,
                    strategy="seasonal_dip_reframe",
                    rationale="Reframing expected seasonal dip against metro benchmarks to prevent unneeded ad spend.",
                    context_data=payload
                )

            # Severe non-seasonal dip: check if actionable
            return CandidateAction(
                action_type="send_message",
                priority=7,
                strategy="perf_dip_intervention",
                rationale=f"Proposing tactical listing/offer intervention for {metric} drop ({delta_pct * 100:.0f}%).",
                context_data=payload
            )

        # -------------------------------------------------------------------------
        # Scenario E: Performance Spikes & Milestones
        # -------------------------------------------------------------------------
        if kind == "perf_spike":
            metric = payload.get("metric", "views")
            return CandidateAction(
                action_type="send_message",
                priority=6,
                strategy="perf_spike_momentum",
                rationale=f"Capitalizing on recent {metric} spike with follow-on conversion nudge.",
                context_data=payload
            )

        if kind == "milestone_reached":
            return CandidateAction(
                action_type="send_message",
                priority=5,
                strategy="milestone_celebration",
                rationale="Leveraging review milestone for social proof and Google post update.",
                context_data=payload
            )

        # -------------------------------------------------------------------------
        # Scenario F: Local Events, Matches, & Category Trends
        # -------------------------------------------------------------------------
        if kind == "ipl_match_today":
            # For restaurants on weekend IPL: shift to delivery rather than dine-in promo
            return CandidateAction(
                action_type="send_message",
                priority=7,
                strategy="ipl_match_strategy",
                rationale="Strategic match-night recommendation adjusting dine-in vs delivery mix.",
                context_data=payload
            )

        if kind == "competitor_opened":
            return CandidateAction(
                action_type="send_message",
                priority=7,
                strategy="competitor_alert",
                rationale="Competitor opening nearby; positioning existing service offerings against competition.",
                context_data=payload
            )

        if kind in ("research_digest", "cde_opportunity"):
            return CandidateAction(
                action_type="send_message",
                priority=6,
                strategy="research_digest",
                rationale="Connecting curated peer research/CDE event to merchant's patient or client cohort.",
                context_data=payload
            )

        if kind in ("category_demand_shift", "category_seasonal"):
            return CandidateAction(
                action_type="send_message",
                priority=6,
                strategy="category_seasonal_shift",
                rationale="Seasonal demand shift recommendation backed by search and sales trends.",
                context_data=payload
            )

        if kind == "festival_upcoming":
            days_until = payload.get("days_until", 30)
            # Restraint test: if festival is 180+ days away with low urgency, silence is appropriate
            if days_until > 90 and trigger.urgency <= 1:
                return None  # Defer: premature outreach
            return CandidateAction(
                action_type="send_message",
                priority=5,
                strategy="festival_campaign",
                rationale=f"Preparation window for {payload.get('festival', 'upcoming festival')}.",
                context_data=payload
            )

        if kind == "gbp_unverified":
            return CandidateAction(
                action_type="send_message",
                priority=7,
                strategy="gbp_verification",
                rationale="Assisting merchant with Google Business Profile verification for search visibility uplift.",
                context_data=payload
            )

        if kind == "curious_ask_due":
            return CandidateAction(
                action_type="send_message",
                priority=4,
                strategy="curious_ask",
                rationale="Weekly low-friction relationship touchpoint gathering demand signals.",
                context_data=payload
            )

        if kind in ("dormant_with_vera", "winback_eligible", "renewal_due"):
            return CandidateAction(
                action_type="send_message",
                priority=6,
                strategy="account_lifecycle",
                rationale="Re-engagement or renewal reminder grounded in account performance.",
                context_data=payload
            )

        # Default fallback: if trigger exists and urgency is reasonable, craft grounded response
        if trigger.urgency >= 2:
            return CandidateAction(
                action_type="send_message",
                priority=5,
                strategy="general_grounded_touchpoint",
                rationale=f"Addressing active {kind} signal with grounded category context.",
                context_data=payload
            )

        # Restraint: low-urgency unclassified triggers produce silence
        return None
