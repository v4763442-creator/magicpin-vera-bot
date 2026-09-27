"""
Magicpin Vera AI Challenge — Candidate Bot HTTP API Server.
Exposes:
- GET  /v1/healthz
- GET  /v1/metadata
- POST /v1/context
- POST /v1/tick
- POST /v1/reply
- POST /v1/teardown
Also exports the official compose() function.
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from magicpin_vera.context_store import store
from magicpin_vera.domain_models import (
    ContextPushRequest, TickRequest, TickResponse, TickActionItem,
    ReplyRequest, ReplyResponse, HealthzResponse, MetadataResponse
)
from magicpin_vera.signal_extractor import (
    NormalizedCategory, NormalizedMerchant, NormalizedTrigger, NormalizedCustomer
)
from magicpin_vera.decision_engine import DecisionEngine
from magicpin_vera.message_composer import MessageComposer, compose
from magicpin_vera.conversation_handlers import ConversationHandler


app = FastAPI(title="Magicpin Vera AI Engine", version="2.0.0")
START_TIME = time.time()


# =============================================================================
# 1. HEALTHZ & METADATA
# =============================================================================

@app.get("/v1/healthz", response_model=HealthzResponse)
async def healthz():
    uptime = int(time.time() - START_TIME)
    counts = store.get_counts()
    return HealthzResponse(
        status="ok",
        uptime_seconds=uptime,
        contexts_loaded=counts
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata():
    return MetadataResponse()


# =============================================================================
# 2. CONTEXT INGESTION
# =============================================================================

@app.post("/v1/context")
async def push_context(body: ContextPushRequest):
    success, resp, status_code = store.push(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload
    )
    return JSONResponse(status_code=status_code, content=resp)


# =============================================================================
# 3. TICK (PERIODIC WAKE-UP & PROACTIVE INITIATION)
# =============================================================================

@app.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest):
    actions: List[TickActionItem] = []
    now_iso = body.now

    for trg_id in body.available_triggers:
        trg_payload = store.get_trigger(trg_id)
        if not trg_payload:
            continue

        trg_data = dict(trg_payload)
        trg_data["id"] = trg_data.get("id", trg_id)
        norm_trg = NormalizedTrigger(trg_data)

        # Identify associated merchant
        merchant_id = norm_trg.merchant_id or norm_trg.payload.get("merchant_id")
        if not merchant_id:
            continue

        mer_payload = store.get_merchant(merchant_id)
        if not mer_payload:
            continue
        norm_mer = NormalizedMerchant(mer_payload)

        # Identify category
        cat_slug = norm_mer.category_slug or norm_trg.payload.get("category", "")
        cat_payload = store.get_category(cat_slug)
        if not cat_payload:
            continue
        norm_cat = NormalizedCategory(cat_payload)

        # Identify customer if customer-scoped
        cust_payload = None
        if norm_trg.customer_id:
            cust_payload = store.get_customer(norm_trg.customer_id)
        norm_cus = NormalizedCustomer(cust_payload)

        # Check suppression
        if norm_trg.suppression_key and store.is_suppressed(norm_trg.suppression_key, now_iso):
            continue

        # Evaluate through Decision Engine
        candidate = DecisionEngine.evaluate_trigger(
            category=norm_cat,
            merchant=norm_mer,
            trigger=norm_trg,
            customer=norm_cus,
            now_iso=now_iso
        )

        # Restraint: If decision engine determined silence, do not add action
        if not candidate:
            continue

        # Compose message
        composed = MessageComposer.compose_from_normalized(
            category=norm_cat,
            merchant=norm_mer,
            trigger=norm_trg,
            customer=norm_cus,
            candidate=candidate
        )

        # Record suppression to avoid duplicate messaging
        if composed.get("suppression_key"):
            store.record_suppression(composed["suppression_key"], norm_trg.expires_at)

        actions.append(TickActionItem(**composed))
        if len(actions) >= 20:  # Official cap: 20 actions per tick
            break

    return TickResponse(actions=actions)


# =============================================================================
# 4. REPLY (RECEIVE MERCHANT / CUSTOMER RESPONSE)
# =============================================================================

@app.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest):
    result = ConversationHandler.handle_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number
    )
    return ReplyResponse(**result)


# =============================================================================
# 5. TEARDOWN (OPTIONAL CLEANUP)
# =============================================================================

@app.post("/v1/teardown")
async def teardown():
    store.wipe_state()
    return {"status": "ok", "message": "Context state successfully wiped."}


# Top-level export of compose()
__all__ = ["app", "compose"]
