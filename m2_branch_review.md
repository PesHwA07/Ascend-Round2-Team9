# M2 Gen-AI Branch Review — `feature/genai-llm`

## Overall Verdict: 🟡 **Integration Required**

M2's implementation of the LLM explainer is robust, includes a solid prompt, timeout handlers, and a deterministic template fallback. However, because M2 and M5 worked in parallel, **there are breaking API contract mismatches between M2's explainer and M5's triage router.**

If we just merge `feature/genai-llm` into our branch right now, the backend will crash during triage.

---

## What M2 Built

| Component | Quality | Notes |
|-----------|---------|-------|
| **Ollama Transport** | ✅ Excellent | Hard timeouts, JSON format mode, connection handling |
| **Prompt Engineering** | ✅ Excellent | Reads from ranking engine perfectly, instructs 15-20 word limits |
| **Fallback System** | ✅ Excellent | Smart deterministic fallbacks based on event keywords if LLM is down |
| **Integration Mismatches** | ❌ Breaking | Returns a Dict instead of a Tuple. Uses different Env Vars. |

---

## 💥 Breaking Conflicts (What we must fix)

### 1. Function Return Signature Mismatch (CRITICAL)

**M5's `triage.py` calls the explainer expecting 3 values:**
```python
explanation, exp_type, action = await generate_explanation(event, item)
```

**M2's `generate_explanation()` now returns a Dictionary with 4 keys:**
```python
{
    "summary": "...", 
    "why_prioritized": "...", 
    "recommended_action": "...", 
    "provider": "ollama" | "fallback"
}
```
**Impact:** `ValueError: too many values to unpack` — the backend will crash on every event ingestion.
**Fix:** We need to update M5's `triage.py` to read the dictionary and map `provider` to `exp_type` ("ollama" -> "ai", "fallback" -> "template").

### 2. Environment Variable Mismatch (Docker Networking)

**M5 & Our Docker Compose:** Uses `OLLAMA_HOST` (e.g. `http://host.docker.internal:11434`)
**M2's Explainer:** Looks for `OLLAMA_BASE_URL`. If missing, it defaults to `http://localhost:11434`.
**Impact:** Inside the Docker container, `localhost` means the container itself, not your Windows host. The LLM connection will fail with "Connection Refused" and it will always trigger the template fallback.
**Fix:** We need to update `docker-compose.yml` and M5's `config.py` to use `OLLAMA_BASE_URL`.

---

## Action Plan

Since M2's logic is great but just misaligned with M5's, we can handle the integration on our branch. 

1. **Merge** `origin/feature/genai-llm` into our branch.
2. **Fix `triage.py`**: Update lines 145-146 to correctly parse M2's dictionary response.
3. **Fix `config.py` & `docker-compose.yml`**: Standardize on `OLLAMA_BASE_URL` so the Docker container can successfully reach Ollama on the host.

Once approved, I'll execute the merge and fixes!
