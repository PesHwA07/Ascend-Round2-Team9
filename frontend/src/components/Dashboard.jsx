import React from 'react'
import EventCard from './EventCard.jsx'

function Dashboard({ 
  triageData, 
  onSelectEvent, 
  isLoading, 
  isOnline, 
  isReplayMode, 
  onExitReplay 
}) {
  const events = triageData?.ranked_events || triageData?.items || []
  const totalEvents = triageData?.total_events || triageData?.total_events_evaluated || events.length
  const executionTime = triageData?.execution_time_ms || 0
  
  // Calculate critical events count
  const criticalCount = events.filter(e => e.severity === 'critical').length

  // Find highest priority score (first event since they are sorted, or search max)
  const highestScore = events.length > 0 
    ? Math.round(Math.max(...events.map(e => e.score || e.priority_score || 0)) * 100)
    : 0

  // 1. Loading Skeleton Screens
  if (isLoading) {
    return (
      <div className="dashboard-container">
        {/* KPI Skeleton Cards */}
        <div className="kpi-grid">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="kpi-card skeleton glass-panel shimmer-bg">
              <div className="skeleton-bar title-bar"></div>
              <div className="skeleton-bar value-bar"></div>
              <div className="skeleton-bar tag-bar"></div>
            </div>
          ))}
        </div>
        
        {/* Feed Header Skeleton */}
        <div className="feed-header">
          <div className="skeleton-bar text-bar" style={{ width: '200px', height: '24px' }}></div>
        </div>

        {/* Feed Skeleton Lists */}
        <div className="incident-feed">
          {[1, 2, 3].map(i => (
            <div key={i} className="event-card skeleton glass-panel shimmer-bg" style={{ minHeight: '120px' }}>
              <div className="skeleton-bar strip-bar"></div>
              <div className="skeleton-content-bars" style={{ padding: '1rem', width: '100%' }}>
                <div className="skeleton-bar bar-long" style={{ width: '40%', height: '14px', marginBottom: '8px' }}></div>
                <div className="skeleton-bar bar-long" style={{ width: '80%', height: '20px', marginBottom: '8px' }}></div>
                <div className="skeleton-bar bar-short" style={{ width: '60%', height: '14px' }}></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // 2. Empty state evaluation
  const showEmptyState = !events || events.length === 0

  return (
    <div className="dashboard-container">
      {/* Replay Mode Visual Notification Banner */}
      {isReplayMode && (
        <div className="replay-warning-banner glass-panel">
          <span className="warning-beacon" aria-hidden="true"></span>
          <span className="warning-text">
            REPLAY MODE — VIEWING ARCHIVED SNAPSHOT (SNAPSHOT ID: {triageData?.triage_id || triageData?.snapshot_id || 'UNKNOWN'})
          </span>
          <button 
            className="exit-replay-btn" 
            onClick={onExitReplay}
            type="button"
          >
            Exit Replay
          </button>
        </div>
      )}

      {/* KPI Operations Metrics Section */}
      <div className="kpi-grid">
        <div className="kpi-card glass-panel">
          <span className="kpi-title">Total Evaluated</span>
          <span className="kpi-value">{totalEvents}</span>
          <span className="kpi-tag">telemetry events</span>
        </div>
        <div className="kpi-card glass-panel critical">
          <span className="kpi-title">Critical Alerts</span>
          <span className="kpi-value">{criticalCount}</span>
          <span className="kpi-tag">immediate response</span>
        </div>
        <div className="kpi-card glass-panel highest-score">
          <span className="kpi-title">Highest Score</span>
          <span className="kpi-value">{highestScore}%</span>
          <span className="kpi-tag">priority peak</span>
        </div>
        <div className="kpi-card glass-panel latency">
          <span className="kpi-title">Processing SLA</span>
          <span className="kpi-value">{executionTime ? `${executionTime.toFixed(0)}ms` : '0ms'}</span>
          <span className="kpi-tag">5s SLA baseline</span>
        </div>
      </div>

      {/* Feed Header and Connection Telemetry */}
      <div className="feed-header">
        <div className="feed-header-left">
          <h2 className="section-title">Prioritized Incident Briefing</h2>
          {isOnline && !isReplayMode && (
            <span className="live-triage-tag">
              <span className="pulse-dot" aria-hidden="true"></span>
              LIVE TRIAGE STREAM
            </span>
          )}
        </div>
        
        {/* Active weights breakdown preview */}
        {triageData?.weights_used && (
          <div className="weights-chip-panel" aria-label="Weights applied for sorting">
            <span className="weights-label">Weights:</span>
            {Object.entries(triageData.weights_used).map(([key, val]) => (
              <span key={key} className="weight-pill">
                {key[0].toUpperCase() + key.slice(1, 3)}: {Math.round(val * 100)}%
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Incident Feed & Empty State Render */}
      {showEmptyState ? (
        <div className="empty-state-feed glass-panel">
          <div className="empty-graphic" aria-hidden="true">🛡️</div>
          <h3 className="empty-title">All Systems Operational</h3>
          <p className="empty-description">
            AuraBrief is listening to the telemetry streams. No incidents are currently flagged in the priority queue.
          </p>
        </div>
      ) : (
        <div className="incident-feed" aria-label="Prioritized incident feed">
          {events.map((event, idx) => (
            <EventCard 
              key={event.event_id || event.id || idx} 
              event={event} 
              onSelect={onSelectEvent} 
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default Dashboard
