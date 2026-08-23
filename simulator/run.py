"""
AuraBrief 95 — Event Simulator (Placeholder)

This is the entry point for the simulator service.
Step 1.4 will add the actual event generation logic for 3 streams:
  - Infrastructure monitoring events
  - Application error events
  - Deployment pipeline events

For now, this just confirms the service starts correctly.
"""
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SIMULATOR] %(message)s")
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://backend:8000")
INTERVAL = int(os.getenv("STREAM_INTERVAL", "5"))


def main():
    logger.info("AuraBrief 95 Simulator starting...")
    logger.info(f"Target API: {API_URL}")
    logger.info(f"Stream interval: {INTERVAL}s")
    logger.info("Waiting for event generation logic (Step 1.4)...")

    # Keep container alive — will be replaced with actual event loop
    while True:
        logger.info("Simulator heartbeat — no events generated yet (placeholder)")
        time.sleep(30)


if __name__ == "__main__":
    main()
