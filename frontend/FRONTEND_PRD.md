# AuraBrief 95 — Frontend Product Requirements Document (Mobile/Frontend)

This document defines the final verified product requirements, design guidelines, component specifications, state management, and integration contracts for the React/Vite responsive frontend of the AuraBrief 95 Hackathon project. It has been aligned with the backend database schemas and the team's API schema contracts.

---

## 1. Objective & Scope

### A. Frontend Objective
The objective is to deliver a premium, responsive web application serving as the operator-facing interface of the AuraBrief 95 AIOps briefing system. The frontend must look like a polished, high-fidelity cyber-ops operations console, optimized for mobile viewing on-the-go while scaling to a desktop grid.

### B. Member 4 Responsibilities (Confirmed Frontend Scope)
*   **Scaffolding:** Setting up the React + Vite frontend environment.
*   **Vanilla CSS Design System:** Writing the stylesheet (`index.css`) containing HSL styling tokens, responsive breakpoints, glassmorphism filters, scrollbars, and keyframe animations from scratch.
*   **Component Implementation:** Designing and implementing all 7 React components: `Header.jsx`, `Dashboard.jsx`, `EventCard.jsx`, `EventDetail.jsx`, `FeedbackPanel.jsx`, `TriageHistory.jsx`, and `AuditLog.jsx`.
*   **Frontend Logic:** Developing loading skeleton states, empty states, error boundaries, and connection-offline recovery screens.
*   **API Client:** Implementing the HTTP request flow using native `fetch` inside `hooks/useApi.js`.
*   **State Management:** Managing active tab selection, weight configurations, incident selection, and Replay Mode.

### C. Outside Member 4 Responsibility (Backend/Team Dependency)
*   **Scoring Math:** Writing the Python algorithm that calculates scores and handles z-score anomalies (Member 1 - AI/ML).
*   **Gen-AI Service:** Prompt engineering, LLM model integration, and error fallback handlers (Member 2 - Gen-AI).
*   **Local Infrastructure:** Dockerfile configuration, Docker Compose networking, and HTTP telemetry simulator (Member 3 - Cloud).
*   **API & DB Engine:** Implementing SQLAlchemy tables, SQLite database management, and exposing routers via FastAPI (Member 5 - Full-stack).

---

## 2. Technical Stack
*   **Framework:** React (Vite-scaffolded for Fast HMR).
*   **Styling:** Vanilla CSS (pure CSS variables, flexbox, grid layouts, and transitions).
*   **Icons:** Lucide React (for lightweight, modern operational status indicators).
*   **API Client:** Native `fetch` API wrapped inside a custom React hook `useApi.js` to manage request state and errors.

---

## 3. UI/UX Design Direction

### A. Theme: "AuraBrief 95 — Premium Glassmorphic Cyber-Ops Operations Console"
To provide a high-end command center aesthetic, the UI uses the following custom styling system:
*   **Canvas Background:** Slate black canvas (`hsl(222, 47%, 6%)`).
*   **Surface Panels:** Elevated slate blocks (`hsl(217, 33%, 12%)`) with rounded borders (`border-radius: 12px`).
*   **Borders:** Semi-transparent bounding lines (`hsla(217, 19%, 20%, 0.5)`) that brighten or glow when active or hovered.
*   **Glassmorphism Accents:** Sticky panels and drawers use semi-transparent backdrops (`hsla(217, 33%, 12%, 0.7)`) backed by browser blur filters (`backdrop-filter: blur(12px)`).
*   **Gradients:** Indigo-to-Cyan linear sweeps (`linear-gradient(135deg, hsl(250, 84%, 63%), hsl(180, 100%, 40%))`) for primary branding, active navigation indicators, and key data aggregates.

### B. Severity HSL Color Coding
*   `critical`: Red/Rose (`hsl(346, 84%, 53%)`)
*   `warning`: Amber/Orange (`hsl(40, 96%, 53%)`)
*   `info`: Cool Cyan (`hsl(180, 100%, 40%)`)
*   `success` (online status): Emerald (`hsl(145, 63%, 49%)`)

### C. Typography
*   **Headings:** **Outfit** (provides geometric shape for titles and priority scores).
*   **Body & Logs:** **Inter** (for dense data reading).
*   **Monospace Elements:** Monospace or system monospaced fonts for raw JSON data viewing.

### D. CSS Micro-Interactions
*   **Incident Cards:** Scale up (`transform: scale(1.01)`) and border glow brightness changes on hover.
*   **Action Elements:** Buttons compress slightly (`transform: scale(0.97)`) on click/press.
*   **Drawers:** Slide in/out dynamically using CSS keyframe transitions.

---

## 4. Responsive Design
*   **Mobile-First Approach:** Base styles are designed for phone viewports (`< 768px`) and scale up to desktop (`≥ 768px`) using CSS media queries.
*   **Touch Targets:** Interactive widgets use a minimum target size of `48px` to support tap safety on mobile screens.
*   **Mobile Behavior (`< 768px`):**
    *   Single-column vertical stack. The incident feed fills the screen width.
    *   The `FeedbackPanel` and `EventDetail` views are hidden behind bottom drawers that slide up from the viewport edge.
    *   No horizontal overflow or sidebar layouts are displayed on mobile.
*   **Desktop Behavior (`≥ 768px`):**
    *   Split-pane layout.
    *   Left column (30% width) permanently houses the `FeedbackPanel` weight controls.
    *   Central column (70% width) displays the active `Dashboard` incident feed.
    *   Selected details (`EventDetail`) slide in as a side panel from the right edge, pushing the triage feed over smoothly.

---

## 5. Complete Component Responsibilities

### Header.jsx
*   **Purpose:** Exposes branding, connection health, and acts as the application's navbar.
*   **UI Elements:** Title branding logo, active navigation tabs (Briefing, History, Logs), and a health indicator beacon.
*   **User Interaction:** Swapping tabs updates active panels. Clicking the logo reloads current triage data.
*   **Mobile Behavior:** Compresses text. Places navigation items inside a horizontal scroll row.
*   **Desktop Behavior:** Wide layout placing logo on the left, navbar tabs in the center, and status beacon on the right.
*   **Data Consumed:** Endpoint response from `/api/health`.

### Dashboard.jsx
*   **Purpose:** Main container displaying counters, active timestamps, and the incident list.
*   **UI Elements:** KPI card deck (total alerts count, critical count, timestamp), list wrapper, and current active weights preview chip.
*   **User Interaction:** Triggers detail overlays on card taps; handles empty state rendering.
*   **Mobile Behavior:** Stacks KPI cards vertically.
*   **Desktop Behavior:** Renders KPI cards side-by-side in a horizontal flex layout.
*   **Data Consumed:** The `ranked_events` list inside the `/api/triage/current` response.

### EventCard.jsx
*   **Purpose:** Summarizes a single operational alert.
*   **UI Elements:** Left border severity colored strip, priority score circular gauge, event title, service/region subtitle, timestamp, and AI explanation snippet.
*   **User Interaction:** Clicking the card selects the incident and triggers the detail view.
*   **Mobile Behavior:** Compact card emphasizing the title and score circle.
*   **Desktop Behavior:** Expanded layouts exposing tags and full timestamps.
*   **Data Consumed:** Single incident object.

### EventDetail.jsx
*   **Purpose:** Inspects detailed information and AI descriptions for an incident.
*   **UI Elements:** Score ring, AI summary card, metadata grid, and collapsible raw JSON inspection panel.
*   **User Interaction:** Toggle switch to expand/collapse raw JSON trees; close button to close overlay.
*   **Mobile Behavior:** Renders as a slide-up bottom drawer.
*   **Desktop Behavior:** Renders as a slide-in side panel.
*   **Data Consumed:** Selected event state object.

### FeedbackPanel.jsx
*   **Purpose:** Lets operators adjust mathematical weights.
*   **UI Elements:** 5 slider controls (Severity, Frequency, Recency, Anomaly, Business Impact), percentage values, budget status ring, and "Apply Weights" CTA.
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
*   **Purpose:** Displays pipeline processing details.
*   **UI Elements:** Terminal console screen, timestamp logs, execution step timings, and SLA validation alerts.
*   **User Interaction:** None (read-only console).
*   **Mobile Behavior:** Narrow columns focusing on duration times.
*   **Desktop Behavior:** Wide terminal rows listing step detail strings.
*   **Data Consumed:** Telemetry list from `/api/audit-log`.

---

## 6. Main Dashboard Design
The main dashboard displays high-priority operational summaries:
*   **Triage KPI Counters:**
    *   `Active Incidents Count` (e.g. `24`)
    *   `Critical Incidents Count` (e.g. `4`)
    *   `Last Triage Run Timestamp` (formatted as `HH:MM:SS`)
*   **Incident Feed:** Sorted list of incident cards descending from the highest calculated priority score.
*   **Priority Score Ring:** An SVG ring gauge wrapping the bold numerical score. The ring's track color changes dynamically:
    *   *Score ≥ 0.80:* Red ring track (Critical urgency).
    *   *Score 0.40 - 0.79:* Amber ring track (Warning urgency).
    *   *Score < 0.40:* Cyan ring track (Info).
*   **Severity Indicators:** A solid vertical color strip on the left margin of each card (Red/Orange/Cyan) indicating raw severity.
*   **AI Summary Preview:** A single-line preview text showing the start of the AI summary snippet.

---

## 7. Event Detail & AI Briefing
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
    *   `Severity Weight` (`severity`)
    *   `Frequency Weight` (`frequency`)
    *   `Recency Weight` (`recency`)
    *   `Anomaly Weight` (`anomaly`)
    *   `Business Impact Weight` (`business_impact`)
*   **Validation Logic:** The sum of all 5 weights must equal exactly 1.0 (100%).
    *   *Balanced (1.0):* Budget tracker ring glows green: `100/100 %`. "Apply Weights" button is active.
    *   *Unbalanced (≠1.0):* Budget ring glows red: `X/100 %`. "Apply Weights" button is disabled with error tooltip: *"Total weights must equal exactly 100%"*.
*   **Action Flow:** Clicking "Apply Weights" calls a `POST` request to `/api/feedback` with the updated JSON payload, replacing the dashboard list with the re-calculated feed instantly.

---

## 9. Triage History & Replay Mode
Allows evaluating previous triage decisions:
*   **Triage Snapshot Card:** Displays snapshot timestamp, weights used, total alerts, and top event title.
*   **Replay Mode Trigger:** Clicking any card switches the dashboard state.
*   **Visual Replay Banner:** A glowing orange banner overlays the top of the interface:
    `⚠️ REPLAY MODE - VIEWING STATIC ARCHIVED SNAPSHOT [TIMESTAMP] [Exit Replay Button]`
*   **Exit Replay:** Clicking "Exit Replay" removes the banner and restores the dashboard to live telemetry `/api/triage/current`.

---

## 10. Audit Log Terminal
Verifies system latency and SLA:
*   **Terminal Visuals:** Monospaced fonts on dark green-black backdrops representing a shell console.
*   **Rows:** Renders individual processing lines: Ingestion time, Scoring formula execution, and LLM text generation. Each shows its elapsed duration (`duration_ms` or `execution_time_ms`) and status.
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

### GET `/api/health`
*   *Response Fields (Confirmed):*
    ```json
    {
      "status": "ok",
      "service": "aurabrief-backend",
      "app_name": "AuraBrief 95",
      "version": "1.0.0",
      "database": "connected",
      "timestamp": "ISO-8601 string"
    }
    ```

### GET `/api/triage/current`
*   *Response Fields (Confirmed):*
    ```json
    {
      "triage_id": "uuid (alias snapshot_id)",
      "generated_at": "ISO-8601 string (alias created_at)",
      "total_events": 42,
      "ranked_events": [
        {
          "event_id": "uuid",
          "source": "string",
          "timestamp": "ISO-8601 string",
          "severity": "critical | warning | info",
          "service": "string",
          "region": "string",
          "title": "string",
          "details": {},
          "tags": ["string"],
          "score": 0.92,
          "score_breakdown": {
            "severity": 0.30,
            "frequency": 0.16,
            "recency": 0.14,
            "anomaly": 0.18,
            "business_impact": 0.14
          },
          "rank": 1,
          "explanation": "string",
          "explanation_type": "ai | template",
          "suggested_action": "string",
          "status": "string"
        }
      ],
      "weights_used": {
        "severity": 0.30,
        "frequency": 0.20,
        "recency": 0.15,
        "anomaly": 0.20,
        "business_impact": 0.15
      }
    }
    ```

### GET `/api/weights`
*   *Response Fields (Confirmed):*
    ```json
    {
      "weights": {
        "severity": 0.30,
        "frequency": 0.20,
        "recency": 0.15,
        "anomaly": 0.20,
        "business_impact": 0.15
      },
      "updated_at": "ISO-8601 string",
      "updated_by": "string"
    }
    ```

### POST `/api/feedback`
*   *Request Payload (Confirmed):*
    ```json
    {
      "weights": {
        "severity": 0.35,
        "frequency": 0.15,
        "recency": 0.15,
        "anomaly": 0.20,
        "business_impact": 0.15
      }
    }
    ```
*   *Response Fields (Confirmed):*
    ```json
    {
      "status": "weights_updated",
      "previous_weights": {},
      "new_weights": {},
      "message": "Weights updated. Re-ranked results included.",
      "triage": {
        "triage_id": "uuid",
        "ranked_events": [ /* items list */ ]
      }
    }
    ```

### GET `/api/triage/history`
*   *Response Fields (Confirmed):*
    ```json
    {
      "total_snapshots": 1,
      "history": [
        {
          "triage_id": "uuid",
          "generated_at": "ISO-8601 string",
          "total_events": 42,
          "top_event_title": "string",
          "top_score": 0.92,
          "weights_used": {}
        }
      ]
    }
    ```

### GET `/api/triage/history/{triage_id}`
*   *Response Fields (Confirmed):*
    *   Returns the full historical `TriageCurrentResponse` matching the selected snapshot UUID.
*   *Replay Route Alias:*
    *   *Path:* `GET /api/triage/replay/{snapshot_id}` (Returns same payload).
    *   *Verification:* **NEEDS TEAM CONFIRMATION** with Member 5 on which route path format to hit during production builds.

### GET `/api/audit-log`
*   *Response Fields (Confirmed):*
    ```json
    {
      "total": 2,
      "logs": [
        {
          "id": 1,
          "timestamp": "ISO-8601 string",
          "level": "info | warning | error",
          "step": "ingest | ranking | explanation",
          "action": "string",
          "actor": "string",
          "message": "string",
          "duration_ms": 120.0
        }
      ]
    }
    ```

---

## 13. State Management Spec

### A. Global State (Managed in App.jsx)
*   `activeTab` (`"brief" | "history" | "audit"`): Swaps visual content panes.
*   `triageData` (Array of objects): Stores ranked items from `/api/triage/current`.
*   `activeWeights` (Object): Active weights mapping.
*   `selectedEvent` (Object | null): Active event object loaded in detail drawers.
*   `isOnline` (boolean): Flag to render offline cover screens.
*   `isReplayMode` (boolean): Controls display of warning replay banners.

### B. Local Component State
*   `FeedbackPanel` $\rightarrow$ `tempWeights` (Object): Holds local slider numbers before Apply triggers.
*   `EventDetail` $\rightarrow$ `isJsonExpanded` (boolean): Expands raw JSON telemetry.

---

## 14. Team Integration Points

*   **Member 1 (AI/ML):** Confirming slider variables match `severity`, `frequency`, `recency`, `anomaly`, and `business_impact`. Displaying scoring breakdown metrics within detail tables.
*   **Member 2 (Gen-AI):** Parsing response payload strings (`explanation`, `suggested_action`) and verifying fallback behavior indicator badges (`explanation_type`).
*   **Member 3 (Cloud):** Assisting in building `frontend/Dockerfile` serving static assets via Node/Vite, exposed on port `5173`.
*   **Member 5 (Full-stack):** Resolving nested `details` log formats and confirming route layouts.

---

## 15. Frontend Folder Structure

```
frontend/
├── public/                 # Static brand assets
├── src/
│   ├── components/         # UI Components
│   │   ├── Header.jsx      # Navigation & Beacon
│   │   ├── Dashboard.jsx   # Feed shell
│   │   ├── EventCard.jsx   # Alert preview
│   │   ├── EventDetail.jsx # Overlay Drawer
│   │   ├── FeedbackPanel.jsx# Sliders & Budget
│   │   ├── TriageHistory.jsx# Historic snapshots
│   │   └── AuditLog.jsx    # Terminal view
│   ├── hooks/              # Native API client hook wrapper
│   │   └── useApi.js
│   ├── utils/              # Metadata formatting helpers
│   │   └── formatters.js
│   ├── App.jsx             # Core layout manager
│   ├── index.css           # Vanilla design variables
│   └── main.jsx            # Bootstrapper script
├── package.json
└── vite.config.js
```

---

## 16. Non-Functional Requirements
*   **Responsive Layout:** Fits viewport widths down to `320px` without horizontal scroll.
*   **Accessibility (A11y):** Keyboard focus support on form elements, semantic markup, and WCAG contrast conformance.
*   **Polish:** Pure CSS animation states and high-fidelity styling variables.
*   **SLA Awareness:** Displays step processing execution latencies.
