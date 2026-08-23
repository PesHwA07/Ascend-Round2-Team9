"""
AuraBrief 95 — Event Generator

Generates realistic simulated events for 3 streams:
  1. infra-monitor  — CPU, memory, disk, container restart events
  2. app-errors     — HTTP 5xx spikes, latency breaches, exceptions, circuit breakers
  3. deploy-events  — Deploys, rollbacks, config changes

Design decisions:
  - Severity distribution: 50% info, 35% warning, 15% critical
    (realistic noise-to-signal so ranking has something to do)
  - Correlated scenarios: a deploy failure can trigger error spikes
    on the same service (makes demo realistic)
  - All timestamps are near "now" (not random dates)
  - Uses only stdlib (random, uuid, datetime) — no extra dependencies
"""
import uuid
import random
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Constants — match API_SCHEMA.md exactly
# ---------------------------------------------------------------------------

SOURCES = ["infra-monitor", "app-errors", "deploy-events"]

SERVICES = ["payment-api", "user-service", "gateway", "order-service", "auth-service"]

REGIONS = ["us-east", "eu-west", "ap-south"]

SEVERITIES = ["critical", "warning", "info"]
SEVERITY_WEIGHTS = [0.15, 0.35, 0.50]  # 15% critical, 35% warning, 50% info

# Service criticality tiers (higher = more critical, used for correlated scenarios)
SERVICE_TIERS = {
    "payment-api": 1,
    "gateway": 1,
    "auth-service": 2,
    "order-service": 2,
    "user-service": 3,
}


# ---------------------------------------------------------------------------
# Stream 1: Infrastructure Monitoring
# ---------------------------------------------------------------------------

INFRA_METRICS = [
    {
        "metric": "cpu_usage",
        "unit": "percent",
        "thresholds": {"critical": 90, "warning": 75, "info": 50},
        "title_template": "CPU usage at {value}% on {service}",
        "tags": ["infrastructure", "performance", "cpu"],
    },
    {
        "metric": "memory_usage",
        "unit": "percent",
        "thresholds": {"critical": 92, "warning": 80, "info": 60},
        "title_template": "Memory usage at {value}% on {service}",
        "tags": ["infrastructure", "performance", "memory"],
    },
    {
        "metric": "disk_usage",
        "unit": "percent",
        "thresholds": {"critical": 95, "warning": 85, "info": 70},
        "title_template": "Disk usage at {value}% on {service}",
        "tags": ["infrastructure", "storage", "disk"],
    },
    {
        "metric": "container_restarts",
        "unit": "count",
        "thresholds": {"critical": 10, "warning": 5, "info": 1},
        "title_template": "Container restarted {value} times on {service}",
        "tags": ["infrastructure", "container", "restart"],
    },
]


def generate_infra_event(severity=None, service=None, region=None):
    """Generate one infrastructure monitoring event."""
    severity = severity or random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]
    service = service or random.choice(SERVICES)
    region = region or random.choice(REGIONS)
    metric_def = random.choice(INFRA_METRICS)

    threshold = metric_def["thresholds"][severity]
    # Value exceeds threshold for warning/critical, stays below for info
    if severity == "critical":
        value = round(threshold + random.uniform(1, 10), 1)
    elif severity == "warning":
        value = round(threshold + random.uniform(0.5, 5), 1)
    else:
        value = round(threshold - random.uniform(5, 20), 1)

    # For container restarts, use integer values (and never negative)
    if metric_def["metric"] == "container_restarts":
        value = max(0, int(value))

    host = f"node-{region}-{random.randint(1, 5):02d}"
    title = metric_def["title_template"].format(value=value, service=service)

    return _build_event(
        source="infra-monitor",
        severity=severity,
        service=service,
        region=region,
        title=title,
        details={
            "metric": metric_def["metric"],
            "metric_value": value,
            "threshold": threshold,
            "unit": metric_def["unit"],
            "host": host,
            "duration_seconds": random.choice([60, 120, 300, 600]),
            # M5's ranking engine reads "container_restarts" for anomaly scoring
            **({"container_restarts": value} if metric_def["metric"] == "container_restarts" else {}),
        },
        tags=metric_def["tags"],
    )


# ---------------------------------------------------------------------------
# Stream 2: Application Errors
# ---------------------------------------------------------------------------

APP_ERROR_TYPES = [
    {
        "error_type": "http_5xx_spike",
        "title_template": "HTTP 5xx spike: {rate}% error rate on {endpoint}",
        "endpoints": ["/api/v1/payments/process", "/api/v1/orders/create", "/api/v1/auth/login", "/api/v1/users/profile"],
        "sample_errors": [
            "java.sql.SQLTransientConnectionException: Connection pool exhausted",
            "io.grpc.StatusRuntimeException: UNAVAILABLE: upstream connect error",
            "redis.exceptions.ConnectionError: Error connecting to Redis",
            "TimeoutError: Request timed out after 30000ms",
        ],
        "tags": ["application", "errors", "http-5xx"],
    },
    {
        "error_type": "latency_p99_breach",
        "title_template": "P99 latency breach: {rate}ms on {endpoint}",
        "endpoints": ["/api/v1/payments/process", "/api/v1/orders/list", "/api/v1/search"],
        "sample_errors": [
            "Slow query: SELECT * FROM orders WHERE ... took 4200ms",
            "Upstream service user-service responded in 3800ms",
            "Cache miss cascade causing repeated DB lookups",
        ],
        "tags": ["application", "latency", "performance"],
    },
    {
        "error_type": "exception_burst",
        "title_template": "Exception burst: {count} errors in {window}s on {service}",
        "endpoints": ["/api/v1/webhooks/process", "/api/v1/notifications/send"],
        "sample_errors": [
            "NullPointerException at PaymentProcessor.java:142",
            "KeyError: 'user_id' in order_handler.py:88",
            "TypeError: Cannot read properties of undefined (reading 'amount')",
        ],
        "tags": ["application", "errors", "exception"],
    },
    {
        "error_type": "circuit_breaker_open",
        "title_template": "Circuit breaker OPEN on {service} → {endpoint}",
        "endpoints": ["/api/v1/payments/process", "/api/v1/auth/verify"],
        "sample_errors": [
            "Circuit breaker tripped: 5 consecutive failures in 60s",
            "Fallback activated: returning cached response",
        ],
        "tags": ["application", "circuit-breaker", "resilience"],
    },
]


def generate_app_error_event(severity=None, service=None, region=None):
    """Generate one application error event."""
    severity = severity or random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]
    service = service or random.choice(SERVICES)
    region = region or random.choice(REGIONS)
    error_def = random.choice(APP_ERROR_TYPES)

    endpoint = random.choice(error_def["endpoints"])
    error_count = {"critical": random.randint(200, 500), "warning": random.randint(50, 200), "info": random.randint(5, 50)}[severity]
    time_window = random.choice([60, 300, 600])
    error_rate = round(random.uniform(1, 5) if severity == "info" else random.uniform(5, 15) if severity == "warning" else random.uniform(15, 40), 1)

    title = error_def["title_template"].format(
        rate=error_rate, endpoint=endpoint, count=error_count,
        window=time_window, service=service,
    )

    return _build_event(
        source="app-errors",
        severity=severity,
        service=service,
        region=region,
        title=title,
        details={
            "error_type": error_def["error_type"],
            "error_count": error_count,
            "time_window_seconds": time_window,
            "endpoint": endpoint,
            "error_rate_percent": error_rate,
            "sample_error": random.choice(error_def["sample_errors"]),
        },
        tags=error_def["tags"],
    )


# ---------------------------------------------------------------------------
# Stream 3: Deployment Pipeline
# ---------------------------------------------------------------------------

DEPLOY_TYPES = [
    {
        "deploy_type": "deploy_started",
        "default_severity": "info",
        "title_template": "Deploy started: {service} {version_to} in {region}",
        "failure_reasons": [],
        "tags": ["deployment", "started", "ci-cd"],
    },
    {
        "deploy_type": "deploy_failed",
        "default_severity": "warning",
        "title_template": "Deploy failed: {service} {version_to} in {region}",
        "failure_reasons": [
            "Health check timeout after 120s",
            "Image pull failed: registry.io/app:v2.4.0 not found",
            "Readiness probe failed: connection refused on port 8080",
            "OOM killed during startup: memory limit 512Mi exceeded",
        ],
        "tags": ["deployment", "failure", "ci-cd"],
    },
    {
        "deploy_type": "rollback_triggered",
        "default_severity": "critical",
        "title_template": "Rollback triggered: {service} reverting to {version_from} in {region}",
        "failure_reasons": [
            "Error rate exceeded 10% threshold post-deploy",
            "Automated rollback: P99 latency > 5000ms for 3 minutes",
            "Manual rollback initiated by on-call engineer",
        ],
        "tags": ["deployment", "rollback", "ci-cd"],
    },
    {
        "deploy_type": "config_change",
        "default_severity": "info",
        "title_template": "Config change applied to {service} in {region}",
        "failure_reasons": [],
        "tags": ["deployment", "config", "ci-cd"],
    },
]

DEPLOYERS = ["ci-bot", "jenkins-pipeline", "github-actions", "deploy-operator"]


def generate_deploy_event(severity=None, service=None, region=None, deploy_type_override=None):
    """Generate one deployment pipeline event."""
    service = service or random.choice(SERVICES)
    region = region or random.choice(REGIONS)

    if deploy_type_override:
        deploy_def = next(d for d in DEPLOY_TYPES if d["deploy_type"] == deploy_type_override)
    else:
        deploy_def = random.choice(DEPLOY_TYPES)

    # Use the default severity for this deploy type, unless overridden
    severity = severity or deploy_def["default_severity"]

    major = random.randint(1, 3)
    minor = random.randint(0, 9)
    patch = random.randint(0, 20)
    version_from = f"v{major}.{minor}.{patch}"
    version_to = f"v{major}.{minor}.{patch + 1}"

    title = deploy_def["title_template"].format(
        service=service, version_from=version_from,
        version_to=version_to, region=region,
    )

    failure_reason = random.choice(deploy_def["failure_reasons"]) if deploy_def["failure_reasons"] else None

    return _build_event(
        source="deploy-events",
        severity=severity,
        service=service,
        region=region,
        title=title,
        details={
            "deploy_type": deploy_def["deploy_type"],
            "version_from": version_from,
            "version_to": version_to,
            "deployed_by": random.choice(DEPLOYERS),
            "commit_sha": uuid.uuid4().hex[:7],
            "failure_reason": failure_reason,
        },
        tags=deploy_def["tags"],
    )


# ---------------------------------------------------------------------------
# Correlated Scenario Generator
# ---------------------------------------------------------------------------

def generate_correlated_scenario():
    """
    Generate a set of correlated events that tell a story.
    Example: deploy fails → error spike → CPU spike on the same service.
    This makes the demo realistic and tests the ranking engine's ability
    to surface related incidents.
    """
    scenario = random.choice(["bad_deploy", "infra_cascade", "routine_noise"])
    service = random.choice(SERVICES)
    region = random.choice(REGIONS)

    if scenario == "bad_deploy":
        # Deploy fails → HTTP errors spike → CPU spikes on the same service
        return [
            generate_deploy_event(service=service, region=region, deploy_type_override="deploy_failed"),
            generate_app_error_event(severity="critical", service=service, region=region),
            generate_infra_event(severity="warning", service=service, region=region),
        ]

    elif scenario == "infra_cascade":
        # Memory critical → container restarts → latency breach on hosted service
        return [
            generate_infra_event(severity="critical", service=service, region=region),
            generate_infra_event(severity="warning", service=service, region=region),
            generate_app_error_event(severity="warning", service=service, region=region),
        ]

    else:
        # Routine noise — low-severity events across different services
        return [
            generate_deploy_event(service=random.choice(SERVICES), region=region, deploy_type_override="config_change"),
            generate_deploy_event(service=random.choice(SERVICES), region=region, deploy_type_override="deploy_started"),
            generate_infra_event(severity="info", service=random.choice(SERVICES), region=region),
        ]


# ---------------------------------------------------------------------------
# Batch Generator (main entry point for the simulator)
# ---------------------------------------------------------------------------

def generate_event_batch(batch_size=None):
    """
    Generate a mixed batch of events.

    Strategy:
      - 30% chance of a correlated scenario (3 related events)
      - Otherwise, 1-3 independent events per stream
    Returns a list of event dicts ready to POST to /api/events/ingest.
    """
    events = []

    if random.random() < 0.30:
        # Correlated scenario — related events on the same service
        events.extend(generate_correlated_scenario())
    else:
        # Independent events — random mix from each stream
        count = batch_size or random.randint(3, 7)
        generators = [generate_infra_event, generate_app_error_event, generate_deploy_event]
        for _ in range(count):
            generator = random.choice(generators)
            events.append(generator())

    return events


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_event(source, severity, service, region, title, details, tags):
    """Construct a standardized event dict matching API_SCHEMA.md."""
    return {
        "event_id": str(uuid.uuid4()),
        "source": source,
        "timestamp": _near_now().isoformat(),
        "severity": severity,
        "service": service,
        "region": region,
        "title": title,
        "details": details,
        "tags": tags,
    }


def _near_now():
    """Return a timestamp within the last 0-60 seconds (simulates slight delay)."""
    offset = random.randint(0, 60)
    return datetime.now(timezone.utc) - timedelta(seconds=offset)
