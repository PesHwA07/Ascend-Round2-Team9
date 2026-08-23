"""
AuraBrief 95 — Simulator Runner

Runs in a loop, generating event batches and POSTing them to the backend
ingest endpoint. Designed to run as a Docker service.

Key behaviors:
  - Waits for backend to be healthy before sending events
  - Retries gracefully on connection failures (backend might not be ready)
  - Logs every batch sent for audit trail visibility
  - Configurable via environment variables
"""
import os
import sys
import time
import json
import logging

import httpx

from generate_events import generate_event_batch

# ---------------------------------------------------------------------------
# Configuration (from environment — set in docker-compose.yml)
# ---------------------------------------------------------------------------
API_URL = os.getenv("API_URL", "http://backend:8000")
INGEST_ENDPOINT = f"{API_URL}/api/events/ingest"
STREAM_INTERVAL = int(os.getenv("STREAM_INTERVAL", "5"))
MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds between retries when backend isn't ready

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIMULATOR] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def wait_for_backend():
    """
    Block until the backend health endpoint responds.
    This runs at startup — the simulator shouldn't send events
    before the backend can accept them.
    """
    health_url = f"{API_URL}/api/health"
    logger.info(f"Waiting for backend at {health_url}...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.get(health_url, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Backend is healthy (attempt {attempt})")
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Backend not ready (attempt {attempt}/{MAX_RETRIES}): {e}")

        time.sleep(RETRY_DELAY)

    logger.error("Backend did not become healthy. Starting anyway — will retry on each batch.")
    return False


def send_batch(events):
    """
    POST a batch of events to the ingest endpoint.
    Returns True if accepted, False on failure.
    """
    payload = {"events": events}

    try:
        resp = httpx.post(
            INGEST_ENDPOINT,
            json=payload,
            timeout=10,
        )

        if resp.status_code == 200:
            result = resp.json()
            logger.info(
                f"Batch accepted: {result.get('received_count', len(events))} events "
                f"| sources: {_summarize_sources(events)}"
            )
            return True
        else:
            logger.warning(f"Backend rejected batch: {resp.status_code} — {resp.text[:200]}")
            return False

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(f"Failed to send batch: {e}")
        return False


def _summarize_sources(events):
    """Count events per source for the log message."""
    counts = {}
    for e in events:
        src = e["source"]
        counts[src] = counts.get(src, 0) + 1
    return ", ".join(f"{src}={count}" for src, count in sorted(counts.items()))


def main():
    """Main event loop — generate and send batches on an interval."""
    logger.info("=" * 60)
    logger.info("AuraBrief 95 — Event Simulator")
    logger.info(f"Target: {INGEST_ENDPOINT}")
    logger.info(f"Interval: {STREAM_INTERVAL}s between batches")
    logger.info("=" * 60)

    wait_for_backend()

    batch_number = 0

    while True:
        batch_number += 1
        events = generate_event_batch()

        # Log event details at debug level (visible if LOG_LEVEL=DEBUG)
        logger.info(f"--- Batch #{batch_number}: {len(events)} events ---")
        for event in events:
            logger.info(
                f"  [{event['severity'].upper():8s}] {event['source']:15s} | "
                f"{event['service']:15s} | {event['title'][:60]}"
            )

        send_batch(events)

        time.sleep(STREAM_INTERVAL)


if __name__ == "__main__":
    main()
