import React, { useState, useEffect } from 'react'
import Header from './components/Header.jsx'
import Dashboard from './components/Dashboard.jsx'
import EventDetail from './components/EventDetail.jsx'
import './index.css'

// Premium mock dataset matching verified schemas & the GenAI structured contract
const MOCK_TRIAGE_DATA = {
  triage_id: "7320b982-f8c6-4b0d-95cf-06f128c7724a",
  snapshot_id: "7320b982-f8c6-4b0d-95cf-06f128c7724a",
  generated_at: "2026-08-23T10:30:00Z",
  created_at: "2026-08-23T10:30:00Z",
  total_events: 42,
  total_events_evaluated: 42,
  execution_time_ms: 182.5,
  summary: "Triaged 42 events across 3 streams. Found 2 critical alerts.",
  weights_used: {
    severity: 0.30,
    frequency: 0.20,
    recency: 0.15,
    anomaly: 0.20,
    business_impact: 0.15
  },
  weights_applied: {
    severity: 0.30,
    frequency: 0.20,
    recency: 0.15,
    anomaly: 0.20,
    business_impact: 0.15
  },
  ranked_events: [
    {
      id: 1,
      event_id: "evt-001",
      source: "infra-monitor",
      timestamp: "2026-08-23T10:28:45Z",
      severity: "critical",
      service: "payment-api",
      region: "us-east",
      title: "Memory usage breach: user container saturated (98%)",
      details: {
        metric_name: "memory_usage",
        utilization_pct: 98,
        container_id: "payment-api-pod-8f1",
        host: "k8s-node-04a",
        limits: "16GiB",
        threshold_percentage: 90
      },
      tags: ["infrastructure", "out-of-memory", "kubernetes"],
      score: 0.94,
      priority_score: 0.94,
      score_breakdown: {
        severity: 0.30,
        frequency: 0.18,
        recency: 0.15,
        anomaly: 0.16,
        business_impact: 0.15
      },
      rank: 1,
      // GenAI contract fields
      summary: "Out-Of-Memory (OOM) threat on payment-api: RAM saturation reached 98%.",
      why_prioritized: "Ranked #1 because payment-api is a Tier-1 critical billing path, and memory utilization breached the 90% threshold by 8% (4.2 standard deviations above baseline).",
      recommended_action: "Restart payment-api containers on Kubernetes node k8s-node-04a and provision secondary replica pods.",
      provider: "ollama",
      status: "open"
    },
    {
      id: 2,
      event_id: "evt-002",
      source: "app-errors",
      timestamp: "2026-08-23T10:27:12Z",
      severity: "critical",
      service: "gateway",
      region: "eu-west",
      title: "HTTP 500 internal server spike on gateway (P99 latency > 8s)",
      details: {
        error_type: "HTTP_500_Spike",
        request_count: 1450,
        error_rate_percent: 12.4,
        p99_latency_seconds: 8.2
      },
      tags: ["application", "gateway-errors", "latency"],
      score: 0.86,
      priority_score: 0.86,
      score_breakdown: {
        severity: 0.30,
        frequency: 0.12,
        recency: 0.14,
        anomaly: 0.18,
        business_impact: 0.12
      },
      rank: 2,
      // GenAI contract fields
      summary: "HTTP 500 errors surged on connection gateway, with response latency exceeding 8.2s.",
      why_prioritized: "Ranked #2 due to a high volume of user traffic impact (1450 requests) and a 12.4% error rate spike, causing gateway timeout cascades.",
      recommended_action: "Verify load balancer connection pooling limits and check upstream user-service response times.",
      provider: "ollama",
      status: "open"
    },
    {
      id: 3,
      event_id: "evt-003",
      source: "deploy-events",
      timestamp: "2026-08-23T10:24:00Z",
      severity: "warning",
      service: "user-service",
      region: "us-east",
      title: "Deploy failed: user-service v2.4.0 rollout rollback triggered",
      details: {
        deploy_type: "deploy_failed",
        version_from: "v2.3.1",
        version_to: "v2.4.0",
        deployed_by: "github-actions-bot",
        commit_sha: "7d10f2b",
        failure_reason: "Health check endpoint timeout on port 8080"
      },
      tags: ["deployment", "ci-cd", "rollback"],
      score: 0.65,
      priority_score: 0.65,
      score_breakdown: {
        severity: 0.15,
        frequency: 0.10,
        recency: 0.12,
        anomaly: 0.13,
        business_impact: 0.15
      },
      rank: 3,
      // GenAI contract fields
      summary: "CI/CD deployment failed on user-service v2.4.0, triggering automatic rollback to version v2.3.1.",
      why_prioritized: "Ranked #3 because deployment rollbacks signify direct production stability changes, though customer impact is mitigated by automatic self-healing rollbacks.",
      recommended_action: "Inspect user-service integration test output in the GitHub Action pipeline logs for commit 7d10f2b.",
      provider: "fallback",
      status: "open"
    },
    {
      id: 4,
      event_id: "evt-004",
      source: "infra-monitor",
      timestamp: "2026-08-23T10:15:00Z",
      severity: "info",
      service: "logger-service",
      region: "ap-south",
      title: "Container restart: fluent-bit logger pod recycled on node-01",
      details: {
        metric_name: "container_restarts",
        restart_count: 1,
        pod_name: "fluent-bit-logger-5x",
        node: "ap-south-node-01"
      },
      tags: ["infrastructure", "logging", "maintenance"],
      score: 0.32,
      priority_score: 0.32,
      score_breakdown: {
        severity: 0.05,
        frequency: 0.08,
        recency: 0.04,
        anomaly: 0.10,
        business_impact: 0.05
      },
      rank: 4,
      // GenAI contract fields
      summary: "fluent-bit logger container restarted automatically on ap-south-node-01 due to log rotation.",
      why_prioritized: "Ranked #4 as a low-severity event. Regular container recycling does not present system operational or security hazards.",
      recommended_action: "No action required. Confirm fluent-bit is running in standby mode and indexing logs.",
      provider: "fallback",
      status: "open"
    }
  ]
}

function App() {
  const [activeTab, setActiveTab] = useState('brief')
  const [triageData, setTriageData] = useState(null)
  const [activeWeights, setActiveWeights] = useState({
    severity: 0.30,
    frequency: 0.20,
    recency: 0.15,
    anomaly: 0.20,
    business_impact: 0.15
  })
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [isOnline, setIsOnline] = useState(true)
  const [isReplayMode, setIsReplayMode] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Load mock triage data on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setTriageData(MOCK_TRIAGE_DATA)
      setIsLoading(false)
    }, 1000)
    return () => clearTimeout(timer)
  }, [])

  // Event Card selection callback handler
  const handleSelectEvent = (event) => {
    setSelectedEvent(event)
    console.log('Selected Event for detailed brief inspection:', event)
  }

  // Triage replay exit handler
  const handleExitReplay = () => {
    setIsReplayMode(false)
    setIsLoading(true)
    setTimeout(() => {
      setTriageData(MOCK_TRIAGE_DATA)
      setIsLoading(false)
    }, 500)
  }

  return (
    <div className="app-shell">
      {/* Background SRE Grid Lines Overlay */}
      <div className="ambient-grid" aria-hidden="true"></div>

      {/* Sticky Glass Navigation Header */}
      <Header 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        isOnline={isOnline} 
      />

      {/* Primary Panels Switcher Router */}
      {activeTab === 'brief' && (
        <Dashboard
          triageData={triageData}
          onSelectEvent={handleSelectEvent}
          isLoading={isLoading}
          isOnline={isOnline}
          isReplayMode={isReplayMode}
          onExitReplay={handleExitReplay}
        />
      )}

      {activeTab === 'history' && (
        <main className="placeholder-container">
          <div className="placeholder-badge">
            <span className="dot yellow" aria-hidden="true"></span>
            <span>Triage History Panel</span>
          </div>
          <h1 className="placeholder-title">Triage Archives</h1>
          <p className="placeholder-description">
            Archived operations briefs. Click a snapshot card here in the future to trigger static Replay Mode across the dashboard.
          </p>
          <div className="system-status-terminal glass-panel">
            <div className="terminal-header">
              <span className="terminal-title">triage_replay_module.sys</span>
            </div>
            <div className="terminal-line">
              <span className="terminal-prompt">&gt;</span>
              <span>listening for snapshot triggers...</span>
            </div>
            <div className="terminal-line">
              <span className="terminal-prompt">&gt;</span>
              <span>replay components: <span className="terminal-value-info">DISCONNECTED (Step 3)</span></span>
            </div>
          </div>
        </main>
      )}

      {activeTab === 'audit' && (
        <main className="placeholder-container">
          <div className="placeholder-badge">
            <span className="dot red" aria-hidden="true"></span>
            <span>Audit logs console</span>
          </div>
          <h1 className="placeholder-title">Latency Diagnostics</h1>
          <p className="placeholder-description">
            Pipeline trace telemetry. Renders step executions and SLA checkpoints in milliseconds.
          </p>
          <div className="system-status-terminal glass-panel">
            <div className="terminal-header">
              <span className="terminal-title">triage_latency_tracker.sys</span>
            </div>
            <div className="terminal-line">
              <span className="terminal-prompt">&gt;</span>
              <span>latency logging stream: <span className="terminal-value-success">STANDBY</span></span>
            </div>
            <div className="terminal-line">
              <span className="terminal-prompt">&gt;</span>
              <span>SLA alert bounds: <span className="terminal-value-info">5000ms SLA TARGET</span></span>
            </div>
          </div>
        </main>
      )}

      {/* Slide-out Drawer / Bottom sheet Overlay */}
      {selectedEvent && (
        <EventDetail 
          event={selectedEvent} 
          onClose={() => setSelectedEvent(null)} 
        />
      )}
    </div>
  )
}

export default App
