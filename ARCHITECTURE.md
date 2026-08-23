# AuraBrief 95 — Architecture & Skill Ownership

> **Document Purpose:** Explains the system architecture, design rationale, and maps every component to the team member's required skill domain.  
> **PRD Deliverable:** "Short architecture note explaining skill ownership."

---

## 1. System Architecture

AuraBrief 95 follows a **three-tier containerized architecture** designed for rapid hackathon development and clean separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                  Presentation Tier                   │
│                                                     │
│   React + Vite (responsive web, mobile-first)       │
│   Glassmorphic cyber-ops console theme              │
│   Components: Dashboard, EventCard, EventDetail,    │
│   FeedbackPanel, TriageHistory, AuditLog            │
│                          │                          │
│                     /api/* proxy                     │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                  Application Tier                    │
│                                                     │
│   FastAPI (Python) — REST API                       │
│   ┌──────────────────────────────────────────────┐  │
│   │  Ingestion   │  Ranking    │  Explanation     │  │
│   │  Router      │  Engine     │  Service         │  │
│   │              │             │                  │  │
│   │  Validates   │  Weighted   │  Ollama LLM or   │  │
│   │  & stores    │  scoring    │  template        │  │
│   │  events      │  formula    │  fallback        │  │
│   └──────────────────────────────────────────────┘  │
│                          │                          │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                    Data Tier                         │
│                                                     │
│   SQLite (file-based, WAL mode)                     │
│   Tables: events, triage_decisions, audit_log,      │
│           ranking_weights                           │
│                                                     │
│   Persisted via Docker volume mount (./data/)       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               External Data Source                   │
│                                                     │
│   Event Simulator (separate Docker service)         │
│   3 streams: infra-monitor, app-errors,             │
│   deploy-events                                     │
│   Sends batches to POST /api/events/ingest          │
└─────────────────────────────────────────────────────┘
```

---

## 2. Key Design Decisions

### 2.1 Ranking: Weighted Scoring over Pure ML

**Decision:** Use a multi-factor weighted scoring formula instead of a trained ML model.

**Rationale:**
- Simulated data provides no real training set for supervised learning
- Weighted scoring is **explainable** — operators see exactly why an event ranked high
- The feedback loop maps directly to adjusting weights, which is intuitive
- Meets the 5-second SLA (scoring is O(n), no model inference overhead)

**Formula:**
```
Score = (w₁ × Severity) + (w₂ × Frequency) + (w₃ × Recency) + (w₄ × AnomalyScore) + (w₅ × BusinessImpact)
```

**Alternative considered:** XGBoost classifier trained on synthetically labeled data. Rejected due to added complexity with no clear benefit on simulated data.

### 2.2 LLM Integration: Ollama with Template Fallback

**Decision:** Use Ollama (locally hosted LLM) for natural-language explanations, with automatic fallback to template-based text.

**Rationale:**
- No cloud API subscription required (constraint)
- Ollama runs on a teammate's laptop — accessible via local network
- Template fallback guarantees the demo never breaks if LLM is unavailable
- Frontend distinguishes sources via `explanation_type` field (`"ai"` vs `"template"`)

### 2.3 Responsive Web over Native Mobile

**Decision:** Build a single responsive web app (React + Vite) rather than a native mobile app.

**Rationale:**
- PRD explicitly allows "mobile-friendly UI (or responsive web)"
- Zero install friction for demo judges (just open a URL)
- One codebase serves both mobile and desktop views
- Faster to build within the 6-hour constraint

### 2.4 SQLite over Cloud Database

**Decision:** Use SQLite for persistence instead of PostgreSQL or a cloud database.

**Rationale:**
- No cloud subscription available (constraint)
- Zero configuration — file-based, starts instantly
- Sufficient for demo scale (dozens of events, not millions)
- Persisted via Docker volume mount for data durability

### 2.5 Separate Simulator Service

**Decision:** Run the event simulator as a standalone Docker service, not inside the backend.

**Rationale:**
- Clean separation — simulates "external" event sources
- Can start/stop independently without affecting backend
- More realistic for the demo ("events arrive from external monitoring")
- M3 (Cloud) owns it entirely, no overlap with M5's backend code

---

## 3. Skill Ownership Map

### Required Skills: `ai-ml`, `cloud`, `gen-ai`, `mobile`

Every feature maps to at least one required skill domain:

| Component | Files | Owner | Skill Domain |
|-----------|-------|-------|-------------|
| **Ranking Engine** | `backend/app/services/ranking.py` | M1 | `ai-ml` |
| Weighted scoring formula | — | M1 | `ai-ml` |
| Anomaly detection (z-score) | — | M1 | `ai-ml` |
| Feedback loop logic | — | M1 | `ai-ml` |
| **LLM Explainer** | `backend/app/services/explainer.py` | M2 | `gen-ai` |
| Ollama/Gemini integration | — | M2 | `gen-ai` |
| Prompt engineering | — | M2 | `gen-ai` |
| Template fallback | — | M2 | `gen-ai` |
| **Docker Infrastructure** | `docker-compose.yml`, `*/Dockerfile` | M3 | `cloud` |
| Event simulator (3 streams) | `simulator/` | M3 | `cloud` |
| Deployment configuration | `.env`, Docker volumes | M3 | `cloud` |
| **Operator Dashboard** | `frontend/src/` | M4 | `mobile` |
| Responsive UI (mobile + desktop) | `frontend/src/index.css` | M4 | `mobile` |
| All visual components | `frontend/src/components/` | M4 | `mobile` |
| **API & Integration** | `backend/app/routers/`, `models.py` | M5 | Full-stack |
| Database models & schemas | `backend/app/models.py`, `schemas.py` | M5 | Full-stack |
| Testing | `backend/tests/` | M5 | Full-stack |

### Skill Coverage Verification

| Required Skill | Where It's Used | Verified |
|---------------|-----------------|----------|
| `ai-ml` | Weighted scoring, anomaly detection, feedback loop | ✅ |
| `cloud` | Docker Compose, Dockerfiles, simulator, volume mounts | ✅ |
| `gen-ai` | Ollama LLM integration, prompt engineering, fallback | ✅ |
| `mobile` | Responsive web UI, mobile-first CSS, touch targets | ✅ |

---

## 4. Data Flow

```
Simulator                Backend                        Frontend
   │                        │                              │
   │  POST /api/events/     │                              │
   │  ingest (batch of      │                              │
   │  3-9 events)           │                              │
   │───────────────────────▶│                              │
   │                        │ 1. Validate schema           │
   │                        │ 2. Store in SQLite           │
   │                        │ 3. Log to audit trail        │
   │                        │                              │
   │                        │◀─────────────────────────────│
   │                        │  GET /api/triage/current     │
   │                        │                              │
   │                        │ 4. Score all events          │
   │                        │ 5. Rank by composite score   │
   │                        │ 6. Generate explanations     │
   │                        │    (LLM or template)         │
   │                        │ 7. Snapshot for replay       │
   │                        │                              │
   │                        │──────────────────────────────▶│
   │                        │  Ranked events + explanations│
   │                        │                              │
   │                        │◀─────────────────────────────│
   │                        │  POST /api/feedback          │
   │                        │  (adjusted weights)          │
   │                        │                              │
   │                        │ 8. Update weights            │
   │                        │ 9. Re-rank with new weights  │
   │                        │                              │
   │                        │──────────────────────────────▶│
   │                        │  Re-ranked results           │
```

---

## 5. Non-Functional Architecture Decisions

| Requirement | Solution |
|-------------|----------|
| **5-second SLA** | Weighted scoring is O(n) — sub-second. LLM runs only on top N events. |
| **6-hour stability** | `restart: unless-stopped` in Docker Compose. SQLite WAL mode for concurrent reads. |
| **Error recovery** | Frontend shows offline overlay with retry. Simulator retries on connection failure. |
| **Audit trail** | Every processing step logged to `audit_log` table with timestamps and durations. |
| **Configuration** | All settings via environment variables, documented in `.env.example`. |
