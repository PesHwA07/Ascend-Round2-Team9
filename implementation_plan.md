# AuraBrief 95 — Implementation Plan

## Objective
Build a mobile AI ops briefing MVP that ingests 3 simulated JSON event streams, ranks/prioritizes incidents using a weighted scoring algorithm + LLM explanations, and ships a responsive operator-facing UI — all demo-able locally via Docker.

---

## Key Technical Decisions

### 1. Ranking Algorithm: Hybrid Weighted Scoring + LLM Explanations

**Research finding:** Industry best practice for AIOps triage is a **multi-factor weighted scoring model**, not a pure ML classifier. This is because:
- With simulated data, we have no real training set for supervised learning
- Weighted scoring is **explainable** — operators can see *why* something ranked high
- The feedback loop naturally maps to **adjusting weights**, which is simple and intuitive

**Formula:**
```
Score = (w1 × Severity) + (w2 × Frequency) + (w3 × Recency) + (w4 × AnomalyScore) + (w5 × BusinessImpact)
```

| Factor | What it measures | Default weight |
|--------|-----------------|----------------|
| Severity | Static level: critical/warning/info | 0.30 |
| Frequency | How often this event type recurred | 0.20 |
| Recency | Time decay — newer events score higher | 0.15 |
| Anomaly Score | Deviation from baseline (simple z-score) | 0.20 |
| Business Impact | Service criticality tier | 0.15 |

**Why not pure ML?** No real training data. A weighted model is transparent, fast, and the feedback loop directly adjusts weights — which is what the bonus feature asks for.

**Why not pure LLM ranking?** Too slow for the 5-second SLA. LLM is used *only* for generating natural-language explanations on the top-ranked items after scoring.

**Alternative you can mention if asked:** XGBoost classifier trained on synthetically labeled data. Discarded because it adds complexity without clear benefit when data is simulated.

---

### 2. Tech Stack

| Layer | Choice | Why | Alternative |
|-------|--------|-----|-------------|
| **Backend** | Python + FastAPI | Async, fast to build, auto-generated OpenAPI docs, great for hackathons | Flask (simpler but no async, no auto docs) |
| **Database** | SQLite via SQLAlchemy | Zero-config, file-based, perfect for local demo, supports replay | PostgreSQL (overkill for local MVP) |
| **Frontend** | React (Vite) + responsive CSS | One codebase for both mobile and web views, fast HMR | React Native Expo (heavier setup, app store friction for demo) |
| **Gen-AI** | Google Gemini API (free tier) or Ollama (local) | Free, generates explanations for top events | OpenAI API (paid, requires key) |
| **Local Cloud** | Docker Compose | Simulates cloud deployment locally, single `docker-compose up` | Direct `python + npm` run (less "cloud-like") |
| **Audit Log** | Structured JSON logging (Python `logging`) | Simple, persistent, queryable | ELK stack (way overkill) |

> [!IMPORTANT]
> **Gen-AI dependency:** We need either a Gemini API key (free at ai.google.dev) or Ollama installed locally for LLM explanations. If neither is available, we fall back to **template-based explanations** (rule-generated text). This ensures the demo never breaks.

---

### 3. Three Simulated Event Streams

Based on the PRD's "multi-region SaaS" context:

| Stream | Source | Example events |
|--------|--------|---------------|
| **Infrastructure Monitoring** | `infra-monitor` | CPU spike, memory exhaustion, disk full, container restart |
| **Application Errors** | `app-errors` | HTTP 500 spike, latency P99 breach, exception burst, circuit breaker open |
| **Deployment Pipeline** | `deploy-events` | Deploy started, deploy failed, rollback triggered, config change |

Each stream posts JSON to a dedicated HTTP endpoint. Events share a common schema:

```json
{
  "event_id": "uuid",
  "source": "infra-monitor | app-errors | deploy-events",
  "timestamp": "ISO-8601",
  "severity": "critical | warning | info",
  "service": "payment-api | user-service | gateway",
  "region": "us-east | eu-west | ap-south",
  "title": "CPU usage at 95%",
  "details": { ... },
  "tags": ["infrastructure", "performance"]
}
```

---

### 4. Persistence & Replay

**Choice: SQLite** with three tables:

| Table | Purpose |
|-------|---------|
| `events` | Raw ingested events |
| `triage_decisions` | Scored/ranked snapshots with explanations |
| `audit_log` | Processing step logs for audit trail |
| `ranking_weights` | Current weight configuration (for feedback loop) |

**Replay:** A `GET /api/triage/history` endpoint returns the last N triage decisions with full event data and scores, enabling replay of past decisions.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Compose                         │
│                                                          │
│  ┌─────────────┐    ┌──────────────────────────────────┐ │
│  │  Simulator   │───▶│         FastAPI Backend          │ │
│  │  (3 streams) │    │                                  │ │
│  └─────────────┘    │  POST /api/events/ingest         │ │
│                     │  GET  /api/triage/current         │ │
│                     │  GET  /api/triage/history         │ │
│                     │  POST /api/feedback               │ │
│                     │  GET  /api/audit-log              │ │
│                     │                                  │ │
│                     │  ┌────────────┐ ┌─────────────┐  │ │
│                     │  │  Ranking   │ │  LLM / Gen  │  │ │
│                     │  │  Engine    │ │  Explanations│  │ │
│                     │  └────────────┘ └─────────────┘  │ │
│                     │          │                        │ │
│                     │     ┌────▼────┐                   │ │
│                     │     │ SQLite  │                   │ │
│                     │     └─────────┘                   │ │
│                     └──────────────────────────────────┘ │
│                              ▲                           │
│  ┌───────────────────────────┴────────────────────────┐  │
│  │           React Frontend (Vite)                    │  │
│  │   Desktop view  │  Mobile view (responsive)       │  │
│  │                                                    │  │
│  │  • Dashboard (ranked events)                       │  │
│  │  • Event detail + explanation                      │  │
│  │  • Feedback controls (adjust weights)              │  │
│  │  • Triage history / replay                         │  │
│  │  • Audit log viewer                                │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure

```
AuraBrief-95/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry, CORS, lifespan
│   │   ├── models.py            # SQLAlchemy models (events, triage, audit)
│   │   ├── database.py          # SQLite connection + session management
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── ingest.py        # POST /api/events/ingest
│   │   │   ├── triage.py        # GET /api/triage/current, /history
│   │   │   ├── feedback.py      # POST /api/feedback (weight adjustment)
│   │   │   └── audit.py         # GET /api/audit-log
│   │   ├── services/
│   │   │   ├── ranking.py       # Weighted scoring engine
│   │   │   ├── explainer.py     # LLM explanation generator
│   │   │   └── audit_logger.py  # Structured audit logging
│   │   └── config.py            # Settings, env vars, defaults
│   ├── simulator/
│   │   ├── generate_events.py   # Generates realistic event batches
│   │   └── stream_runner.py     # Sends events to API on interval
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       ├── test_ranking.py
│       ├── test_ingest.py
│       └── test_feedback.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css            # Design system, responsive breakpoints
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    # Main ranked events view
│   │   │   ├── EventCard.jsx    # Individual event with score + explanation
│   │   │   ├── EventDetail.jsx  # Expanded event detail modal
│   │   │   ├── FeedbackPanel.jsx # Weight adjustment sliders (bonus)
│   │   │   ├── TriageHistory.jsx # Replay past decisions
│   │   │   ├── AuditLog.jsx     # Processing step log viewer
│   │   │   └── Header.jsx       # Navigation + branding
│   │   ├── hooks/
│   │   │   └── useApi.js        # API fetch hooks
│   │   └── utils/
│   │       └── formatters.js    # Date, score formatting
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.yml
├── README.md                    # Setup instructions (deliverable)
├── ARCHITECTURE.md              # Skill ownership note (deliverable)
└── DEMO_SCRIPT.md               # Demo script outline (deliverable)
```

---

## Team Skill Ownership (5 members)

| Member | Skill Area | Ownership |
|--------|-----------|-----------|
| **Member 1** | **AI/ML** | Ranking engine (`ranking.py`), scoring formula, anomaly detection, feedback loop logic |
| **Member 2** | **Gen-AI** | LLM integration (`explainer.py`), prompt engineering, explanation generation, fallback templates |
| **Member 3** | **Cloud** | Docker Compose, Dockerfile configs, deployment setup, CI/local infra, simulator |
| **Member 4** | **Mobile** | React frontend (mobile-responsive), Dashboard, EventCard, FeedbackPanel, all responsive CSS |
| **Member 5** | **Full-stack / Integration** | API routes, database models, Pydantic schemas, testing, README, architecture docs |

> [!NOTE]
> This maps directly to the PRD constraint: *"Required skills only: ai-ml, cloud, gen-ai, mobile."* Member 5 ties it together.

---

## Phased Build Plan (6-Hour Timeline)

### Phase 1: Foundation (Hour 0–1.5)
| Step | Owner | Task | Verify |
|------|-------|------|--------|
| 1.1 | M5 | Init repo, project structure, `docker-compose.yml` | `docker-compose up` starts cleanly |
| 1.2 | M5 | SQLite models + database setup | Tables created on startup |
| 1.3 | M5 | Pydantic schemas for events | Schema validates sample JSON |
| 1.4 | M3 | Event simulator (3 streams) | Generates valid JSON batches |
| 1.5 | M4 | React project scaffold + design system (CSS) | App loads in browser, responsive |

### Phase 2: Core Pipeline (Hour 1.5–3.5)
| Step | Owner | Task | Verify |
|------|-------|------|--------|
| 2.1 | M5 | Ingest endpoint `POST /api/events/ingest` | Events stored in SQLite |
| 2.2 | M1 | Ranking engine (weighted scoring) | Scored events returned in order |
| 2.3 | M2 | LLM explainer integration | Top events get NL explanations |
| 2.4 | M5 | Triage endpoint `GET /api/triage/current` | Returns ranked + explained events |
| 2.5 | M5 | Audit logger service | Processing steps logged to DB |
| 2.6 | M4 | Dashboard UI (ranked events list) | Events display with scores |
| 2.7 | M3 | Simulator → API integration | Events flow end-to-end |

### Phase 3: Features & Polish (Hour 3.5–5)
| Step | Owner | Task | Verify |
|------|-------|------|--------|
| 3.1 | M4 | Event detail modal + explanation display | Tap card → see detail + explanation |
| 3.2 | M1+M4 | Feedback panel (weight sliders) — BONUS | Adjust weights → re-rank works |
| 3.3 | M5 | Triage history endpoint + replay | Past decisions retrievable |
| 3.4 | M4 | History/replay UI view | Can browse past triage snapshots |
| 3.5 | M4 | Audit log viewer UI | Processing steps visible |
| 3.6 | ALL | Error states (API failures, empty states) | Clear recovery messages shown |

### Phase 4: Demo Prep (Hour 5–6)
| Step | Owner | Task | Verify |
|------|-------|------|--------|
| 4.1 | M3 | Docker Compose final test | `docker-compose up` runs full stack |
| 4.2 | M5 | README with setup instructions | New user can follow steps |
| 4.3 | M5 | ARCHITECTURE.md (skill ownership) | Maps features → skills |
| 4.4 | ALL | DEMO_SCRIPT.md | Step-by-step demo walkthrough |
| 4.5 | ALL | End-to-end dry run | Full flow in < 5 seconds |

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|---------|---------|
| `POST` | `/api/events/ingest` | Receive batch of events from any stream |
| `GET` | `/api/triage/current` | Get current ranked/prioritized events with explanations |
| `GET` | `/api/triage/history` | Replay past triage decisions |
| `POST` | `/api/feedback` | Adjust ranking weights (bonus) |
| `GET` | `/api/weights` | Get current ranking weights |
| `GET` | `/api/audit-log` | View processing step logs |
| `GET` | `/api/health` | Health check |

---

## Verification Plan

### Automated Tests
```bash
# Backend unit tests
pytest backend/tests/ -v

# Verify 5-second SLA
pytest backend/tests/test_ranking.py::test_triage_under_5_seconds
```

### Manual Verification
- `docker-compose up` → full stack starts
- Simulator sends events → appear ranked in dashboard
- Adjust weights via feedback panel → rankings change
- View triage history → past decisions are shown
- Mobile browser test (Chrome DevTools responsive mode)
- Error state: kill backend → frontend shows recovery message

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| No Gemini API key / Ollama not installed | No LLM explanations | Template-based fallback explanations (already planned) |
| 5-second SLA missed due to LLM latency | NFR violation | LLM runs async; scoring is instant; explanations are pre-generated for top N only |
| SQLite concurrent write contention | Data loss under load | Single-writer pattern + WAL mode; acceptable for demo scale |
| Docker not installed on demo machine | Can't demo | Fallback: run backend + frontend directly with `uvicorn` + `npm run dev` |

---

## Open Questions for Team

> [!IMPORTANT]
> 1. **Gemini API key** — Does anyone on the team have a Google AI Studio API key? If not, should we go with Ollama (local LLM) or template-based explanations?
> 2. **Docker availability** — Is Docker installed on the demo machine? If not, we'll need the direct-run fallback.
> 3. **Git repo** — Where are we hosting? GitHub? Do we have it set up?
