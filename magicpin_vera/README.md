# Magicpin Vera AI Challenge — Solution Documentation

## 1. Architectural Overview

The solution implements an **8-stage, context-grounded decision and composition engine** that decouples trigger detection from communication:

```
Context Store (Thread-safe, versioned, 409 conflict on stale)
  ↓
Signal Extraction & Dynamic Normalization (Category, Merchant, Trigger, Customer)
  ↓
Trigger Evaluation & Restraint Filter (Trigger ≠ Action; silence is rewarded)
  ↓
Candidate Action Generation & Contextual Decision Engine
  ↓
Message Composition (Dynamic category voice, Hindi-English code-mix, Kaleyra outbound templates)
  ↓
Validation & Safety Guards (Zero URLs, zero taboos, verified entity provenance)
  ↓
Multi-Turn Conversation State Machine (Auto-reply breaker, intent transition to action, hostile opt-out)
  ↓
FastAPI HTTP Service (GET /healthz, GET /metadata, POST /context, POST /tick, POST /reply, POST /teardown)
```

---

## 2. Key Design Decisions & Strategies

### Dynamic Category Voice (No Hardcoded Overfitting)
- Extracts `voice.tone`, `vocab_allowed`, and `vocab_taboo` dynamically from incoming `CategoryContext` payloads.
- Automatically tailors tone to the vertical:
  - **Dentists**: Clinical peer tone (`peer_clinical`), `Dr.` salutation, verifiable citations with page/source references.
  - **Salons**: Warm and practical (`warm_practical`), focusing on service-at-price and bridal timelines.
  - **Restaurants**: Fellow-operator register (`fellow_operator`), tactical covers/delivery shift advice during match nights.
  - **Gyms**: Disciplined coach register (`coach_to_member`), reframing seasonal attendance dips without discount panics.
  - **Pharmacies**: Trustworthy and precise (`trustworthy_precise`), molecule precision, batch recall alerts, senior-citizen care.

### Trigger ≠ Action & Intentional Restraint
- Proactive messages are only sent when there is a timely, grounded, and actionable merchant/customer benefit.
- Low-urgency premature triggers (e.g. festivals 6+ months away) or expected seasonal shifts without viable interventions return silence (`actions: []`).

### Strict Zero Hallucination & Fact Provenance
- All numbers, prices, dates, batch IDs, and customer slots are extracted strictly from provided context.
- Expired offers are strictly filtered out; only verified active catalog offers are referenced.
- URLs are strictly blocked (preventing Meta template rejections and judge penalties).

### Multi-Turn Conversational Robustness
- **Auto-Reply Loop Breaker**: Detects canned WhatsApp Business auto-replies; backs off with `action: "wait"` on Turn 2 and gracefully closes with `action: "end"` on Turn 3+.
- **Intent Transition**: When a merchant agrees ("Ok let's do it", "Yes please"), immediately switches to action execution with actioning keywords (`done`, `draft`, `confirm`, `proceed`) and zero qualifying questions.
- **Hostile / Opt-Out**: Immediately closes with `action: "end"` and suppresses further outreach.
- **Out-of-Scope**: Politely declines non-domain queries (e.g. GST filing) and redirects back to growth topics.

### Determinism & Latency Performance
- 100% deterministic, offline-capable core with average tick latency of **~4.4ms**, far below the official 30-second budget.
- Optional LLM rephraser sits behind a feature flag (`USE_LLM=false` by default) with automatic fallback.

---

## 3. Official Deliverables & Verification

- **`bot.py`**: Production FastAPI server exposing all 5 official endpoints + `/v1/teardown` and the official `compose(...)` function.
- **`submission.jsonl`**: Exactly 30 verified lines generated from `expanded/test_pairs.json`, completely free of URLs and category taboos.
- **`conversation_handlers.py`**: Multi-turn handler implementing `respond(state, merchant_message)`.
- **`test_harness.py`**: 5 comprehensive test suites covering versioning, API contracts, 30 canonical cases, adversarial replays, and benchmarks (all 5 pass).
- **`run_judge_simulation.py`**: Runs official `challenge_pack/judge_simulator.py` against the running bot (warmup, context push, auto-reply, intent transition, hostility all PASS).
