# Gen-AI Explanation Layer (AuraBrief 95)

> **Architectural principle: Ranking determines priority. Gen-AI explains the ranking.**
> The weighted scoring engine decides *which* incidents matter and in what order.
> The LLM never ranks, never reorders, never recalculates scores — it only explains
> the ranking engine's output to an on-call operator.

Owner: Gen-AI team member (`feature/genai-llm`).

---

## What it does

For every triage run, the ranking engine scores up to 100 events and produces a
ranked list (`backend/app/services/ranking.py` → `rank_events()`). The Gen-AI
service then generates short natural-language explanations for **only the top N**
(default 5, set by `TOP_N_EXPLANATIONS` in the backend config):

```
events → ranking engine → ranked list → top N → explainer.py → Ollama
                                                       ↓
                                    {summary, why_prioritized, recommended_action}
                                                       ↓
                                            Triage API response
```

Structured output per incident (agreed Gen-AI contract):

```json
{
  "summary": "what happened",
  "why_prioritized": "why the scoring engine ranked it here",
  "recommended_action": "first thing the operator should investigate",
  "provider": "ollama | fallback"
}
```

## Requirements

- [Ollama](https://ollama.com) installed locally (`brew install ollama`)
- A small instruction-following model pulled:

```bash
ollama pull llama3.2:3b     # default; fits the 5-second SLA on laptop hardware
```

`qwen3:8b` also works but needs ~5-6s per explanation on typical Macs — use it
only on faster machines via `OLLAMA_MODEL=qwen3:8b`.

## Configuration

All settings are environment variables (see `.env.example`). When the backend
package is present, values may alternatively live in `backend/app/config.py`
(`Settings`) under the same names.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_ENABLED` | `true` | Master switch. `false` = template fallback only |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama daemon endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model tag (anything in `ollama list`) |
| `OLLAMA_TIMEOUT` | `6.0` | Hard per-request timeout (seconds) |
| `OLLAMA_NUM_PREDICT` | `150` | Max tokens generated per explanation |
| `LLM_COOLDOWN_SECONDS` | `60` | Circuit-breaker window after a failure |

No secrets are required — Ollama runs fully local.

## Running Ollama

```bash
ollama serve                # usually already running as a service
ollama list                 # confirm llama3.2:3b is present
```

Quick manual test of the model:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Reply with exactly: OK",
  "stream": false,
  "think": false,
  "options": {"num_predict": 10}
}'
```

## How the explanation service works

`backend/app/services/explainer.py`:

1. **Prompt** (`build_prompt`) — renders an AIOps-assistant prompt containing the
   event fields *and* the ranking engine's scores verbatim (rank, priority score,
   severity/blast/anomaly/recurrence breakdown), plus hard rules: never change the
   ranking, never invent facts, answer in ≤20-word fields.
2. **Transport** (`call_ollama`) — plain `httpx` POST to `/api/generate` with
   `"format": "json"` (forces valid JSON), `"think": false` (skips reasoning
   tokens on qwen3 models), temperature 0.2, hard timeout.
3. **Validation** (`parse_explanation`) — tolerates markdown fences / trailing
   text, then enforces exactly three non-empty string fields (length-capped).
4. **Fallback** — any failure (Ollama down, unreachable, cold model, slow, HTTP
   error, malformed/empty output, unexpected exception) returns a deterministic
   template explanation built from the *same* event/ranking data, in the same
   contract shape with `provider: "fallback"`, categorised into infrastructure /
   application-error / deployment / security / generic patterns. Templates never
   claim the LLM produced them.
5. **Circuit breaker** — after one failure the LLM is skipped for
   `LLM_COOLDOWN_SECONDS`, so a batch never queues behind repeated timeouts.

Public API:

```python
# Agreed contract (never raises):
{
  "summary", "why_prioritized", "recommended_action", "provider"
} = await generate_explanation(event, ranking_data)

# Legacy triage-router shape ((explanation_text, suggested_action)):
explanation_text, suggested_action = await generate_explanation_pair(event, ranking_data)

# Concurrent top-N helper (wall-clock ≈ one LLM round-trip):
await generate_explanations_for_ranked(ranked_items, top_n=3)
```

Events may be SQLAlchemy `Event` models or plain dicts. Ranking data is read-only:
the module consumes whatever component scores the engine supplies — both the
current backend vocabulary (`severity_score`, `blast_radius_score`,
`anomaly_score`, `recurrence_score`, `priority_score`) and the PRD wording
(`frequency_score`, `recency_score`, `business_impact_score`, `final_score`) —
and never computes or writes back any value (asserted in tests).

## Reliability & the 5-second SLA

- Only top-N events hit the LLM; ranking itself is instant and independent.
- Hard timeout per request; failures fall back in milliseconds (connection
  refused) or at worst one timeout window (circuit breaker prevents repeats).
- Measured on the reference MacBook Air (2026): top-2 explanations ≈ **2.9s**
  wall-clock with a warm `llama3.2:3b`. Cold model loads can exceed the
  timeout — run `ollama run llama3.2:3b "hi"` once before demoing to warm it.
- If Ollama is entirely absent, the demo still works end-to-end with templates.

## Running the Gen-AI tests

Tests mock all Ollama traffic (`httpx.MockTransport`) — no live server needed:

```bash
pip install pytest pytest-asyncio httpx
pytest backend/tests/test_explainer.py -v      # 21 tests
pytest                                          # whole suite once merged
```

Covered: LLM success, JSON-mode request shape, unreachable server (+circuit
breaker), timeout, HTTP 500, malformed text, missing/empty JSON keys, markdown
fences, disabled flag, all five fallback categories, prompt rules/rank context,
ranking-input immutability, dict-shaped events, empty-event safety.

## Integration notes (for the backend/integration team)

- The existing router call `explanation, action = await generate_explanation(event, item)`
  maps 1:1 onto `generate_explanation_pair(event, item)` — same tuple, same
  guarantees. Alternatively adopt the contract dict via
  `await generate_explanation(event, item)`.
- To use the faster concurrent path, replace the per-item loop with
  `await generate_explanations_for_ranked(ranked_items, top_n=settings.TOP_N_EXPLANATIONS)`
  then read `item["explanation"] / item["suggested_action"] /
  item["explanation_provider"]`.
- Optional: add the six `OLLAMA_*` / `LLM_COOLDOWN_SECONDS` fields from
  `.env.example` to `backend/app/config.py::Settings` so values flow through the
  existing settings object instead of raw env vars.
