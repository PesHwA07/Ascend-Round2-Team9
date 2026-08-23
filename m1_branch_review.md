# M1 AI/ML Branch Review — `feature/ranking-engine`

## Overall Verdict: 🔴 **Duplicate of M5's work — needs alignment discussion**

M1 wrote a clean standalone ranking engine, but **M5 already built and integrated a ranking engine** directly into the backend. Both do the same job, so the team needs to decide which one to use.

---

## What M1 Built (1 file, 291 lines)

| Feature | Quality | Notes |
|---------|---------|-------|
| **Severity scoring** | ✅ Good | Maps critical→1.0, high→0.75, etc. |
| **Anomaly detection** | ✅ Good | Keyword-based + error_rate from payload |
| **Recurrence scoring** | ✅ Good | Counts same event_type+service matches |
| **Blast radius** | ✅ Good | Environment + region + service keywords |
| **Weight normalization** | ✅ Good | Auto-normalizes to sum=1.0 |
| **Feedback loop** | ✅ Good | `adjust_weights()` function included |

---

## 💥 Critical Problem: M1 and M5 Built Different Ranking Engines

### Factor Name Mismatch

| M1's 4 Factors (`src/ranking.py`) | M5's 5 Factors (`backend/app/services/ranking.py`) |
|---|---|
| `severity` (0.30) | `severity` (0.30) ✅ |
| `blast_radius` (0.25) | `business_impact` (0.15) ⚠️ |
| `anomaly` (0.25) | `anomaly` (0.20) ✅ |
| `recurrence` (0.20) | `frequency` (0.20) ⚠️ |
| ❌ missing | `recency` (0.15) ❌ |

**M1 uses 4 factors. M5 uses 5 factors.** The frontend sliders, database schema, feedback API, and triage response all use M5's 5-factor names.

### Score Scale Mismatch

| | M1 | M5 |
|---|---|---|
| **Score range** | 0–100 | 0.0–1.0 |
| **Priority labels** | Returns "critical"/"high"/"medium"/"low" | No labels, uses numeric score |

### Input Format Mismatch

| | M1 | M5 |
|---|---|---|
| **Input type** | Plain `Dict` (expects `event.get("raw_payload")`) | SQLAlchemy ORM `Event` object (uses `event.details`) |
| **File location** | `src/ranking.py` (standalone) | `backend/app/services/ranking.py` (integrated) |

---

## The Real Situation

M5 already built and integrated a working ranking engine that:
- ✅ Is wired into `triage.py`
- ✅ Reads from the SQLite database via ORM
- ✅ Uses 5 factors matching the frontend sliders
- ✅ Has been tested end-to-end (we proved it with the integration test)

M1's engine is a clean standalone module but:
- ❌ Not wired into the backend
- ❌ Uses different factor names (`blast_radius` vs `business_impact`, `recurrence` vs `frequency`)
- ❌ Missing `recency` factor entirely
- ❌ Works on plain dicts, not ORM objects
- ❌ Located in wrong path (`src/` instead of `backend/app/services/`)

---

## What to Tell M1

> "Hey M1, M5 already integrated a ranking engine into the backend that's wired to the database and triage pipeline. Your standalone module is good code, but it uses different factor names and is missing the `recency` factor.
> 
> To avoid conflicts, can you:
> 1. **Rename** `blast_radius` → `business_impact` and `recurrence` → `frequency`
> 2. **Add** a `recency` factor (time-decay: recent events score higher)
> 3. **Move** your file from `src/ranking.py` to `backend/app/services/ranking.py`
> 4. **Accept ORM Event objects** instead of plain dicts (use `event.severity` instead of `event.get('severity')`)
> 5. **Change score range** from 0-100 to 0.0-1.0 to match the frontend
> 
> OR we can just use M5's version since it's already integrated and tested. Your `adjust_weights()` function is nice though — M5 doesn't have that as a standalone utility. We could merge just that part."
