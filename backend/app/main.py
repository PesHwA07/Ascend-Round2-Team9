"""
AuraBrief 95 - Minimal FastAPI entry point.
This placeholder provides a health check so Docker Compose can verify
the backend is running. M5 (full-stack) will add the real routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AuraBrief 95",
    description="AI Ops Briefing System - Event Triage & Ranking",
    version="0.1.0",
)

# CORS: allow frontend dev server and any local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """Health endpoint used by Docker Compose healthcheck and monitoring."""
    return {"status": "ok", "service": "aurabrief-backend"}
