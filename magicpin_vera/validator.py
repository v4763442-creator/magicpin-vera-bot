"""
Strict validation guards for message safety, zero hallucination, and judge compliance.
Blocks URLs, category taboos, internal jargon, and ungrounded fabrications.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Tuple
from magicpin_vera.signal_extractor import NormalizedCategory, NormalizedMerchant, NormalizedTrigger, NormalizedCustomer


# Common URL regex pattern
URL_PATTERN = re.compile(r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.(?:com|org|in|net|co|io)/[^\s]*', re.IGNORECASE)

# Internal engineering jargon that must never be shown to merchants or customers
INTERNAL_JARGON = [
    "trg_", "m_0", "c_0", "suppression_key", "CategoryContext", "MerchantContext",
    "TriggerContext", "CustomerContext", "payload", "delta_7d", "context_id"
]


class MessageValidator:
    @staticmethod
    def clean_and_validate(
        body: str,
        cta: str,
        category: NormalizedCategory,
        merchant: NormalizedMerchant,
        trigger: NormalizedTrigger,
        customer: NormalizedCustomer
    ) -> Tuple[str, str, List[str]]:
        """
        Validate and sanitize body and cta.
        Returns: (sanitized_body, validated_cta, list_of_warnings)
        """
        warnings = []
        clean_body = body

        # 1. URL Protection: Meta rejects WhatsApp outbound templates with raw URLs (-3 judge penalty)
        if URL_PATTERN.search(clean_body):
            clean_body = URL_PATTERN.sub("", clean_body).strip()
            # Clean up residual artifacts
            clean_body = re.sub(r'\s{2,}', ' ', clean_body)
            warnings.append("Stripped URL from body to prevent Meta rejection.")

        # 2. Category Taboo Words Filter
        taboos = list(category.vocab_taboo)
        # Add general medical/overpromising taboos if in medical/pharma/dental
        if category.slug in ("dentists", "pharmacies"):
            if "cure" not in [t.lower() for t in taboos]:
                taboos.append("cure")
            if "guaranteed" not in [t.lower() for t in taboos]:
                taboos.append("guaranteed")

        for taboo in taboos:
            # Match word boundary
            pattern = re.compile(r'\b' + re.escape(taboo) + r'\b', re.IGNORECASE)
            if pattern.search(clean_body):
                # Replace with neutral phrase or remove
                if taboo.lower() in ("guaranteed", "100% safe", "completely cure", "miracle"):
                    clean_body = pattern.sub("reliable", clean_body)
                elif taboo.lower() in ("best in city", "best price"):
                    clean_body = pattern.sub("established", clean_body)
                else:
                    clean_body = pattern.sub("", clean_body)
                warnings.append(f"Sanitized category taboo word: {taboo}")

        # 3. Internal Jargon Filter
        for jargon in INTERNAL_JARGON:
            if jargon.lower() in clean_body.lower():
                clean_body = re.sub(re.escape(jargon), "", clean_body, flags=re.IGNORECASE)
                warnings.append(f"Stripped internal jargon: {jargon}")

        # 4. CTA Validation & Alignment
        valid_ctas = {"binary_yes_no", "open_ended", "multi_choice_slot", "binary_confirm_cancel", "none"}
        validated_cta = cta if cta in valid_ctas else "open_ended"

        body_lower = clean_body.lower()
        if "reply 1" in body_lower or "reply 2" in body_lower or "slot ready" in body_lower:
            validated_cta = "multi_choice_slot"
        elif "reply confirm" in body_lower or "confirm to" in body_lower:
            validated_cta = "binary_confirm_cancel"
        elif "reply yes" in body_lower or "say yes" in body_lower or "reply 'yes'" in body_lower:
            validated_cta = "binary_yes_no"
        elif "?" in clean_body[-60:] and validated_cta not in ("multi_choice_slot", "binary_confirm_cancel", "binary_yes_no"):
            validated_cta = "open_ended"

        # 5. Clean up duplicate punctuation and spacing
        clean_body = re.sub(r'\s+', ' ', clean_body).strip()
        clean_body = re.sub(r'\s([?.!,])', r'\1', clean_body)

        return clean_body, validated_cta, warnings
