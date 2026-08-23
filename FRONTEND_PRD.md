# AuraBrief 95 — Frontend Product Requirements Document (Mobile/Frontend)

This document defines the product requirements, user interface specs, component architecture, and integration contracts for the React/Vite responsive frontend of the AuraBrief 95 Hackathon project. It acts as the definitive specification for the Mobile/Frontend Engineer (Member 4) and is prepared for team verification before coding begins.

---

## 1. Objective & Scope

### A. Frontend Objective
The objective is to deliver a premium, responsive web application serving as the operator-facing interface of the AuraBrief 95 AIOps briefing system. The frontend must look state-of-the-art and function as a high-fidelity cyber-ops console, optimized for mobile viewing on-the-go while scaling to a desktop grid.

### B. Member 4 Responsibilities (In-Scope)
*   Scaffolding the React + Vite frontend environment.
*   Writing all visual CSS styling from scratch using Vanilla CSS to implement the custom design system.
*   Designing and implementing all 7 visual components: `Header`, `Dashboard`, `EventCard`, `EventDetail`, `FeedbackPanel`, `TriageHistory`, and `AuditLog`.
*   Developing frontend state management, loading skeletons, error boundaries, empty queues, and connection-offline recovery screens.
*   Integrating with backend API endpoints over HTTP, parsing data payloads, and managing the active weights state loop.

### C. Out of Scope (Responsibilities of Other Team Members)
*   Coding the Python weighted-scoring mathematical engine or z-score anomaly calculation (`ranking.py` - Member 1).
*   Writing LLM prompt configurations, connecting to Google Gemini/Ollama, or creating text fallback libraries (`explainer.py` - Member 2).
*   Writing backend `Dockerfiles`, configuring root `docker-compose.yml`, or scripting the mock event simulator (Member 3).
*   Exposing FastAPI routes, configuring SQLite tables, compiling Pydantic contracts, or managing DB CRUD integrations (Member 5).

---

## 2. Technical Stack
*   **Core UI Library:** React (Vite-scaffolded for fast Hot Module Replacement).
*   **Styling System:** Vanilla CSS (CSS variables, flexbox, grid, media queries, CSS keyframe animations).
*   **Icon Library:** Lucide React (for lightweight operational status and action indicators).
*   **API Client:** Native browser `fetch` API wrapped inside a custom React hook `useApi`.

---

## 3. UI/UX Design Direction

### A. Theme: "AuraBrief 95 — Premium Glassmorphic Cyber-Ops Operations Console"
To match high-performance, real-world Site Reliability Engineering (SRE) tools, the visual layout moves away from basic dashboard grids to a dark operations room aesthetic:
*   **Canvas Background:** Slate black canvas (`hsl(222, 47%, 6%)`).
*   **Surfaces:** Elevated slate blocks (`hsl(217, 33%, 12%)`) with rounded borders (`border-radius: 12px`).
*   **Borders:** Semi-transparent bounding lines (`hsla(217, 19%, 20%, 0.5)`) which brighten or glow when active or hovered.
*   **Glassmorphic Accents:** Sticky panels and drawers use background color mixtures (`hsla(217, 33%, 12%, 0.7)`) backed by browser glass blur filters (`backdrop-filter: blur(12px)`).
*   **Gradients:** Indigo-to-Cyan linear sweeps (`linear-gradient(135deg, hsl(250, 84%, 63%), hsl(180, 100%, 40%))`) for primary branding, active navigation indicators, and action triggers.

### B. Typography
*   **Font Selection:** Headings use **Outfit** (providing geometric shape), and body/logs use **Inter** (for dense data reading).
*   **Monospace Font:** JetBrains Mono or local system monospace for logs and details codes.

### C. CSS Micro-Interactions
*   **Feed Cards:** Scale up (`transform: scale(1.01)`) with a soft glow shadow on hover.
*   **Tabs:** Active navigation pills move with a slide-and-fade CSS transition.
*   **CTAs:** Buttons compress slightly (`transform: scale(0.97)`) on click/press.
*   **Drawers:** Slide in/out dynamically using CSS slide keyframes (`cubic-bezier(0.16, 1, 0.3, 1)`).

---

## 4. Responsive Design
*   **Mobile-First Approach:** Layout styles start with phone viewports (`< 768px`) and use media queries to upscale to tablet/desktop widths (`≥ 768px`).
*   **Touch Targets:** Interactive controls (sliders, tab navigation, list items) use a minimum clickable height of `48px` to guarantee tap safety on mobile screens.
*   **Mobile Behavior (`< 768px`):**
    *   Single-column grid. Main incident feed fills the screen.
    *   Sliders (`FeedbackPanel`) and expanded item details (`EventDetail`) are hidden behind bottom drawers that slide up from the screen bottom when triggered.
    *   No horizontal overflow; layout wraps elements into vertical stacks.
*   **Desktop Behavior (`≥ 768px`):**
    *   Multi-column split-pane. 
    *   Left column (30% width) permanently docks the weight feedback sliders (`FeedbackPanel`).
    *   Central column displays the main `Dashboard` incident list.
    *   Selected details (`EventDetail`) slide in as a side panel on the right margin, avoiding modal overlaps.

---

## 5. Complete Component Responsibilities

### Header.jsx
*   **Purpose:** Houses navigation tabs and exposes backend health telemetry.
*   **UI Elements:** Title logo, active navigation tabs (Briefing, History, Logs), and a health indicator dot.
*   **User Interaction:** Switching tabs changes the active screen panel. Clicking the logo reloads current triage data.
*   **Mobile Behavior:** Links pack into a horizontal swipeable navbar; titles compress.
*   **Desktop Behavior:** Grid layout spreading elements to edges.
*   **Data Consumed:** State of `/api/health` connection.

### Dashboard.jsx
*   **Purpose:** The central workspace holding counters, triage timestamps, and the incident card feed.
*   **UI Elements:** KPI card deck (total alerts, critical count, timestamp), list wrapper, and current weights preview pill.
*   **User Interaction:** Triggers event detail drawers on card taps; manages empty state rendering.
*   **Mobile Behavior:** Stacks KPIs vertically.
*   **Desktop Behavior:** Spreads KPIs into a horizontal flex row.
*   **Data Consumed:** List of ranked incidents from `/api/triage/current`.

### EventCard.jsx
*   **Purpose:** Summarizes a single operational alert.
*   **UI Elements:** Colored severity tag strip, priority score circular gauge, event title, service/region subtitle, timestamp, and AI explanation snippet.
*   **User Interaction:** Clicking anywhere on the card container sets this event as active.
*   **Mobile Behavior:** Compact cards emphasizing the title and score circle.
*   **Desktop Behavior:** Expanded layouts exposing tags and timestamps.
*   **Data Consumed:** Single incident object.

### EventDetail.jsx
*   **Purpose:** The deep-dive inspection card for an incident.
*   **UI Elements:** Circular score ring, AI summary card, metadata table, and collapsible raw JSON drawer.
*   **User Interaction:** Toggle switch to expand/collapse raw JSON trees; close button to dim modal.
*   **Mobile Behavior:** Renders as a slide-up bottom drawer.
*   **Desktop Behavior:** Renders as a slide-in side panel.
*   **Data Consumed:** Active event state object.

### FeedbackPanel.jsx
*   **Purpose:** Lets operators adjust mathematical weights.
*   **UI Elements:** 5 slider tracks, percentage values, budget status ring, and "Apply Weights" CTA.
*   **User Interaction:** Dragging sliders updates local weights; clicking "Apply" locks state.
*   **Mobile Behavior:** Hidden under a bottom-right FAB, opens as a bottom drawer.
*   **Desktop Behavior:** Fixed sidebar on the left.
*   **Data Consumed:** Active weights from `/api/weights`.

### TriageHistory.jsx
*   **Purpose:** Lists archived triage runs to support playback.
*   **UI Elements:** Snapshot lists (timestamps, weights, top alerts) and replay activation buttons.
*   **User Interaction:** Clicking a card triggers Replay Mode; clicking the replay banner exits back to live mode.
*   **Mobile & Desktop Behavior:** List representation, desktop converts it into a dual timeline grid.
*   **Data Consumed:** Historic snapshots metadata from `/api/triage/history`.

### AuditLog.jsx
*   **Purpose:** Displays processing details.
*   **UI Elements:** Terminal console screen, timestamp logs, execution step timings, and SLA validation alerts.
*   **User Interaction:** None (read-only console).
*   **Mobile Behavior:** Narrow columns focusing on duration times.
*   **Desktop Behavior:** Wide terminal rows listing step detail strings.
*   **Data Consumed:** Telemetry list from `/api/audit-log`.

---

## 6. Main Dashboard Design
The main screen organizes high-priority data points:
*   **Triage KPI Counters:**
    *   `Active Incidents Count` (e.g. `24`)
    *   `Critical Incidents Count` (e.g. `4`)
    *   `Last Triage Run Timestamp` (formatted as `HH:MM:SS`)
*   **Incident Feed:** Sorted list of incident cards descending from the highest calculated priority score.
*   **Priority Score Ring:** A stylized SVG ring gauge showing the overall score.
    *   *Score > 80:* Red ring track (Critical urgency).
    *   *Score 40 - 80:* Amber ring track (Warning urgency).
    *   *Score < 40:* Cyan ring track (Info).
*   **Severity Indicators:** A solid vertical color strip on the left margin of each card (Red/Orange/Cyan) indicating raw severity.
*   **AI Summary Preview:** A single-line preview text showing the start of the AI summary snippet.

---

## 7. Event Detail / AI Briefing
Selecting any incident card opens the full investigation panel:
*   **Layout:** Responsive bottom drawer on mobile, static side panel on desktop.
*   **Sparkling AI Briefing Card:** Highlights the natural-language explanation. Uses an indigo background glow and Sparkle icon.
*   **Explanation Badge:** Differentiates the generator source dynamically using the `explanation_type` API field:
    *   `explanation_type == "ai"`: Displays green badge `"Live AI Summary"`.
    *   `explanation_type == "template"`: Displays gray badge `"Template Brief"`.
*   **Raw Incident Metadata:** Renders a key-value grid parsing standard log parameters.
*   **Dynamic JSON Viewer:** Includes an expandable toggle labeled "Inspect Raw JSON" which exposes the nested `details` sub-dictionary formatted with monospaced indentation.

---

## 8. Feedback Panel (Live Re-ranking)
Allows operators to customize the triage algorithm.
*   **Five Sliders:**
    *   `Severity Weight`
    *   `Frequency Weight`
    *   `Recency Weight`
    *   `Anomaly Score Weight`
    *   `Business Impact Weight`
*   **Validation Logic:** The sum of all 5 weights must equal exactly 100%.
    *   *Balanced (100%):* Budget tracker ring glows green: `100/100 %`. "Apply Weights" button is active.
    *   *Unbalanced (≠100%):* Budget ring glows red: `X/100 %`. "Apply Weights" button is disabled with error tooltip: *"Total weights must equal exactly 100%"*.
*   **Action Flow:** Clicking "Apply Weights" calls a `POST` request to `/api/feedback` with the updated JSON payload, replacing the dashboard list with the re-calculated feed instantly.

---

## 9. Triage History & Replay Mode
Allows evaluating previous triage decisions:
*   **Triage Snapshot Card:** Displays snapshot timestamp, weights used, total alerts, and top 3 event titles.
*   **Replay Mode Trigger:** Clicking any card switches the dashboard state.
*   **Visual Replay Banner:** A glowing orange banner overlays the top of the interface:
    `⚠️ REPLAY MODE - VIEWING STATIC ARCHIVED SNAPSHOT [TIMESTAMP] [Exit Replay Button]`
*   **Exit Replay:** Clicking "Exit Replay" removes the banner and restores the dashboard to live telemetry `/api/triage/current`.

---

## 10. Audit Log Terminal
Verifies system latency and SLA:
*   **Terminal Visuals:** Monospaced fonts on dark green-black backdrops representing a shell console.
*   **Rows:** Renders individual processing lines: Ingestion time, Scoring formula execution, and LLM text generation. Each shows its elapsed duration (`duration_ms`) and status.
*   **5-Second SLA Tracker:**
    *   *Total time < 5000ms:* Displays green glowing badge `[SLA PASSED - XXms]`.
    *   *Total time ≥ 5000ms:* Displays flashing red warning badge `[SLA BREACHED - XXms]`.

---

## 11. Loading, Error, and Empty States
*   **Skeleton Screens:** Custom shimmer elements that mimic the cards load during network queries. Shimmer effect is coded using moving CSS gradient transitions.
*   **Backend Offline State:** If backend drops offline (health check fails), a full-screen blurred overlay displays:
    `📡 Lost connection to Ops Stream. Retrying in X seconds... [Retry Button]`
*   **Empty State:** If the database active table contains 0 incidents, the dashboard displays:
    `🛡️ System Clear. No active operational incidents reported.`

---

## 12. API Integration Contract
The frontend requires the following API integrations, communicating via JSON:

### Endpoints Details

*   **`GET /api/health`**
    *   *Description:* Heartbeat check.
    *   *Confirmed Fields:* `{"status": "ok"}` or `{"status": "degraded"}`
*   **`GET /api/triage/current`**
    *   *Description:* Retrieves active sorted incident feed.
    *   *Confirmed Fields:* Array of objects containing:
        *   `event_id` (string)
        *   `title` (string)
        *   `source` (string)
        *   `severity` (string)
        *   `service` (string)
        *   `region` (string)
        *   `timestamp` (string)
        *   `score` (number)
        *   `explanation` (string)
        *   `details` (nested JSON dictionary)
    *   *Unconfirmed Fields (Need Confirmation from Member 5):*
        *   `explanation_type`: Does the backend send this field (`"ai"` or `"template"`) to let the frontend render the appropriate badge?
*   **`GET /api/weights`**
    *   *Description:* Retrieves default weights.
    *   *Confirmed Fields:* None.
    *   *Unconfirmed Fields (Need Confirmation from Member 5):*
        *   Exact key names of the weights. E.g., `{"severity": float, "frequency": float, "recency": float, "anomaly_score": float, "business_impact": float}` vs abbreviated keys.
*   **`POST /api/feedback`**
    *   *Description:* Submits custom weights and receives re-ranked lists.
    *   *Confirmed Fields:* None.
    *   *Unconfirmed Fields (Need Confirmation from Member 5):*
        *   Does this endpoint accept the weights payload and return the newly sorted event array matching the payload format of `/api/triage/current` directly?
*   **`GET /api/triage/history`**
    *   *Description:* Retrieves previous triage snapshots.
    *   *Confirmed Fields:* None.
    *   *Unconfirmed Fields (Need Confirmation from Member 5):*
        *   Does this return metadata list of runs (e.g. `[{"snapshot_id": string, "timestamp": string, "weights": {}}]`), or does it return the full list of nested event arrays inside each historical item?
*   **`GET /api/audit-log`**
    *   *Description:* Retrieves pipeline timing statistics.
    *   *Confirmed Fields:* None.
    *   *Unconfirmed Fields (Need Confirmation from Member 5):*
        *   Exact response format. E.g. array of timing logs `[{"step": string, "duration_ms": number, "status": string, "timestamp": string}]`.

---

## 13. State Management Spec

### A. Global State Variables (Managed in App.jsx)
*   `activeTab` (`"brief" | "history" | "audit"`): Swaps current workspace pane.
*   `triageData` (Array of objects): Main database of current active sorted events.
*   `activeWeights` (Object): Active weights mapping.
*   `selectedEvent` (Object | null): Active event object loaded in detail drawers.
*   `isOnline` (boolean): Flag for offline screens.
*   `isReplayMode` (boolean): Controls display of warning replay banners.

### B. Component Local State
*   `FeedbackPanel` $\rightarrow$ `tempWeights` (Object): Active slider positions before apply triggers.
*   `EventDetail` $\rightarrow$ `isJsonExpanded` (boolean): Controls JSON inspection panel layout.

---

## 14. Team Integration Points

*   **Member 1 (AI/ML):** Connect UI sliders to backend keys. Show calculations (anomaly z-scores, recency time-decay metrics) inside event details to verify the ML math.
*   **Member 2 (Gen-AI):** Render summary layouts. Distinguish template outputs from live AI using the `explanation_type` indicator.
*   **Member 3 (Cloud):** Compile a frontend static build `Dockerfile` container binding port outputs correctly in `docker-compose.yml`.
*   **Member 5 (Full-stack):** Agree on event `details` JSON payload formats to ensure the UI renders key-values cleanly. Set up CORS on all FastAPI routers.

---

## 15. Frontend Folder Structure

```
frontend/
├── public/                 # Static asset folders
├── src/
│   ├── components/         # Visual components
│   │   ├── Header.jsx
│   │   ├── Dashboard.jsx
│   │   ├── EventCard.jsx
│   │   ├── EventDetail.jsx
│   │   ├── FeedbackPanel.jsx
│   │   ├── TriageHistory.jsx
│   │   └── AuditLog.jsx
│   ├── hooks/              # API custom hook wrappers
│   │   └── useApi.js
│   ├── utils/              # Metadata formatting helpers
│   │   └── formatters.js
│   ├── App.jsx             # Core layout manager
│   ├── index.css           # Design system variable sets
│   └── main.jsx            # Launch root script
├── package.json
└── vite.config.js
```

---

## 16. Non-Functional Requirements
*   **Responsive Layout:** Adapts smoothly down to a minimum mobile viewport of `320px` width without content clipping or horizontal scrolling.
*   **Accessibility (A11y):** Form fields and slider controls use semantic `<label>` bindings. Visual outlines match Indigo highlights. Color contrast follows WCAG AAA.
*   **Visual Polish:** Constant application of glassmorphic layers, accent glows, and CSS transition micro-interactions.
*   **SLA Awareness:** Displays execution logs cleanly in milliseconds to verify compliance with the 5-second processing SLA.
