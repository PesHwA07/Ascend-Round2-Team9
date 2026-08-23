# AuraBrief 95

# AuraBrief 95

Title:
AuraBrief 95

Background:
A multi-region SaaS team streams product and infrastructure events into a cloud data plane. Rules-based triage creates noise and hides real incidents.

Problem Statement:
In 6 hours, build a mobile AI ops brief system using only ai-ml, cloud, gen-ai, mobile: ingest three simulated JSON event streams, apply ranking/AI where applicable, and ship an operator-facing experience.

Scope:
Deliver a demoable mobile AI ops brief MVP focused on ingestion, ranking, and operator UX. Do not expand into unrelated specialty domains outside the required skills.

MVP Scope:
- Ingest at least three simulated JSON event streams over HTTP
- Implement scoring/ranking logic appropriate to the required skills
- Ship a mobile-friendly UI (or responsive web) showing prioritized items with explanations
- Log processing steps for a basic audit trail
- Deploy on cloud-friendly infrastructure suitable for a live demo
- Generate short natural-language explanations for top-ranked items

Advanced/Bonus Scope:
Add an operator feedback loop that adjusts ranking weights during the demo.

Functional Requirements:
- Ingest simulated event streams from at least three sources
- Produce prioritized/ranked outputs with short explanations
- Expose results through UI and/or API suitable for a live demo
- Persist enough state to replay the last triage decisions
- Keep all features within the required skill set

Non-Functional Requirements:
- End-to-end triage path completes within 5 seconds for a sample batch
- Demo remains usable for a 6-hour hackathon window
- UI/API failures show clear recoverable error states
- Configuration is documented in README

Constraints:
- MVP must be built and demoed within 6 hours
- Required skills only: ai-ml, cloud, gen-ai, mobile
- Use simulated data only (no production systems)
- No specialty domains outside the required skills list
- Team size is fixed to 5

Deliverables:
- Working demo of the triage/ranking flow
- Source repository with setup instructions
- Short architecture note explaining skill ownership
- Demo script or recording outline
