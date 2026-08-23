# AuraBrief 95 — Demo Script

> **Purpose:** Step-by-step walkthrough for the live demo.  
> **Duration:** 8-10 minutes.  
> **PRD Deliverable:** "Demo script or recording outline."

---

## Pre-Demo Checklist

- [ ] Docker Compose running (`docker-compose up`)
- [ ] All 3 services healthy (backend, frontend, simulator)
- [ ] Ollama running on M2's laptop (or template fallback confirmed)
- [ ] Browser open at `http://localhost:5173`
- [ ] Mobile device or Chrome DevTools responsive mode ready
- [ ] Simulator generating events (check logs)

---

## Demo Flow

### Act 1: The Problem (1 min)

**Narrator says:**

> "We're a multi-region SaaS team. Our infrastructure generates hundreds of alerts daily — CPU spikes, error surges, failed deployments. Rules-based triage creates noise and hides real incidents. Operators waste time sifting through low-priority alerts while critical issues get buried."

**Show:** Point to the simulator logs in the terminal — events flooding in every 5 seconds from 3 different sources.

> "These events come from three monitoring streams: infrastructure metrics, application errors, and the deployment pipeline. Right now, they're just raw noise."

---

### Act 2: Intelligent Triage (3 min)

**Action:** Switch to the AuraBrief dashboard in the browser.

> "AuraBrief 95 ingests these events and applies a weighted scoring algorithm to surface what actually matters."

**Show:**
1. **KPI counters** — Total alerts, critical count, last triage timestamp
2. **Ranked incident feed** — Events sorted by priority score (highest first)
3. **Score rings** — Red (critical), amber (warning), cyan (info)

> "Each event gets a composite priority score based on five factors: severity, frequency, recency, anomaly detection, and business impact."

**Action:** Click on the top-ranked event to open the detail panel.

**Show:**
4. **Score breakdown** — How each factor contributed to the final score
5. **AI explanation** — Natural language summary of why this event matters
6. **Explanation badge** — "Live AI Summary" (green) vs "Template Brief" (gray)

> "The system generates a natural-language brief using an LLM, explaining *why* this incident was flagged as the top priority. If the AI is unavailable, it falls back to template-based explanations — the system never breaks."

---

### Act 3: Operator Feedback Loop (2 min)

**Action:** Open the Feedback Panel (sidebar on desktop, bottom drawer on mobile).

> "Operators aren't passive consumers. They can tune the ranking algorithm in real-time."

**Show:**
1. **Five weight sliders** — Severity, Frequency, Recency, Anomaly, Business Impact
2. **Budget ring** — Shows total weight allocation (must equal 100%)

**Action:** Drag the "Business Impact" slider up and "Frequency" slider down.

> "If an operator knows that business impact matters more during a revenue-critical window, they can boost that weight."

**Action:** Click "Apply Weights."

**Show:**
3. **Dashboard re-ranks instantly** — Events reshuffle based on new weights
4. **New weights reflected** in the weights preview pill

> "The feed re-ranks immediately. Payment-api incidents now surface higher because we increased business impact weight."

---

### Act 4: Triage History & Replay (1.5 min)

**Action:** Switch to the "History" tab.

> "Every triage decision is snapshotted. Operators can replay past decisions to review what happened."

**Show:**
1. **Triage snapshot cards** — Timestamp, weights used, top events
2. Click a past snapshot

**Show:**
3. **Replay mode banner** — Orange warning: "REPLAY MODE — VIEWING ARCHIVED SNAPSHOT"
4. **Historical ranked feed** — Exactly as it appeared at that time

> "This is critical for post-incident review. You can see what the system surfaced, what weights were active, and whether the right incidents were prioritized."

**Action:** Click "Exit Replay" to return to live mode.

---

### Act 5: Audit Trail & SLA (1 min)

**Action:** Switch to the "Logs" tab.

> "For compliance and observability, every processing step is logged."

**Show:**
1. **Terminal-style audit log** — Ingestion, scoring, explanation generation
2. **Duration timestamps** — How long each step took
3. **SLA badge** — Green "SLA PASSED — 320ms" or the 5-second threshold indicator

> "The entire triage path — from event ingestion to ranked output — completes in under 5 seconds, meeting our SLA requirement."

---

### Act 6: Mobile Experience (1 min)

**Action:** Open Chrome DevTools → Toggle device toolbar → Select iPhone 14 Pro.

*(Or show on an actual phone if available.)*

> "The entire experience is mobile-first. Operators can check the ops brief on-the-go."

**Show:**
1. **Single-column layout** — Cards stack vertically
2. **Bottom drawer** — Event detail slides up from bottom
3. **FAB button** — Opens feedback panel as bottom sheet
4. **Touch-friendly** — All targets are 48px minimum

> "Same functionality, optimized for touch. No pinch-zooming, no horizontal scrolling."

---

### Act 7: Architecture & Tech (30 sec)

> "Under the hood: three Docker services — a Python FastAPI backend, a React frontend, and an event simulator. SQLite for persistence, Ollama for LLM inference, and a weighted scoring engine that's fully explainable and tunable in real-time."

**Show:** Quick flash of the architecture diagram from `ARCHITECTURE.md`.

---

## Closing Statement

> "AuraBrief 95 transforms raw operational noise into prioritized, AI-explained incident briefs — with an operator feedback loop that puts humans in control of the algorithm. Built in 6 hours by a team of 5."

---

## Anticipated Q&A

| Question | Answer |
|----------|--------|
| "Why not a trained ML model?" | Simulated data has no real training set. Weighted scoring is explainable, fast, and the feedback loop directly adjusts weights. |
| "What if the LLM goes down?" | Template-based fallback kicks in automatically. The UI shows a gray "Template Brief" badge so operators know. |
| "How does it scale?" | SQLite handles demo scale. For production: swap to PostgreSQL, add Redis caching, deploy on Kubernetes. |
| "Is the 5-second SLA reliable?" | Scoring is O(n) — sub-second. LLM is the bottleneck, so we only explain the top N events. Measured and logged in the audit trail. |
| "Why responsive web instead of native mobile?" | Zero install friction for demo judges. One codebase, two views. PRD allows it. |
