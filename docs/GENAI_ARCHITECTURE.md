# AuraBrief 95 Gen-AI Explainer Architecture

## Overview

The Gen-AI layer explains already prioritized incidents.

The ranking engine makes the decision.
The Gen-AI layer explains the decision.

Principle:

```
Ranking = Decision
Gen-AI  = Explanation
```

## Architecture Flow

```
Event Streams
      |
      v
FastAPI Backend
      |
      v
Ranking Engine
      |
      | Ranked incidents + score breakdown
      |
      v
Gen-AI Explainer
      |
      +----------------+
      |                |
      v                v
Ollama             Fallback
llama3.2:3b        Template
      |                |
      +----------------+
              |
              v
Structured Explanation
```

## Gen-AI Input

Function:

```python
generate_explanation(event, ranking_data)
```

Event:

- event_id
- source
- timestamp
- severity
- service
- region
- title
- details
- tags

Ranking data:

- rank
- score
- score breakdown

## Gen-AI Output

```json
{
  "summary": "...",
  "why_prioritized": "...",
  "recommended_action": "...",
  "provider": "ollama | fallback"
}
```

## Ollama Configuration

Model:

- llama3.2:3b

Environment:

- `OLLAMA_HOST`
- `OLLAMA_MODEL`

## Fallback Behaviour

Fallback is used when:

- Ollama server unavailable
- timeout
- model unavailable
- invalid response
- malformed output
- unexpected exception

Fallback uses the same event and ranking information.

## Why LLM is not used for ranking

Reasons:

- no real production training data
- weighted scoring is explainable
- ranking must be deterministic
- avoids LLM latency for every incident
