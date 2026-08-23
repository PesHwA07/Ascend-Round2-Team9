import React from 'react'

function TriageHistory({ 
  historyList, 
  onReplaySnapshot, 
  isLoading, 
  error, 
  onRefresh 
}) {

  // Loading skeleton state
  if (isLoading) {
    return (
      <main className="placeholder-container">
        <div className="placeholder-badge">
          <span className="dot yellow" aria-hidden="true"></span>
          <span>Loading Archives...</span>
        </div>
        <div className="incident-feed" style={{ width: '100%', maxWidth: '720px' }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="history-card skeleton glass-panel shimmer-bg" style={{ minHeight: '110px', marginBottom: '1rem' }}>
              <div className="skeleton-content-bars" style={{ padding: '1.2rem', width: '100%' }}>
                <div className="skeleton-bar" style={{ width: '30%', height: '12px', marginBottom: '10px' }}></div>
                <div className="skeleton-bar" style={{ width: '90%', height: '18px', marginBottom: '10px' }}></div>
                <div className="skeleton-bar" style={{ width: '50%', height: '12px' }}></div>
              </div>
            </div>
          ))}
        </div>
      </main>
    )
  }

  // Error state
  if (error) {
    return (
      <main className="placeholder-container">
        <div className="placeholder-badge">
          <span className="dot red" aria-hidden="true"></span>
          <span>Connection Failures</span>
        </div>
        <div className="empty-state-feed glass-panel" style={{ border: '1px dashed var(--state-critical)' }}>
          <div className="empty-graphic">📡</div>
          <h3 className="empty-title" style={{ color: 'var(--state-critical)' }}>Failed to Sync Archives</h3>
          <p className="empty-description" style={{ marginBottom: '1.5rem' }}>
            {error}
          </p>
          <button 
            onClick={onRefresh} 
            className="exit-replay-btn" 
            style={{ background: 'var(--state-critical)' }}
            type="button"
          >
            Retry Connection
          </button>
        </div>
      </main>
    )
  }

  const list = historyList || []
  const isEmpty = list.length === 0

  // Helper to format timestamps
  const formatTime = (timeStr) => {
    if (!timeStr) return 'N/A'
    try {
      const date = new Date(timeStr)
      return date.toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    } catch (e) {
      return timeStr
    }
  }

  return (
    <main className="placeholder-container" style={{ minHeight: 'calc(100vh - 160px)', padding: '2rem 1rem' }}>
      <div className="placeholder-badge">
        <span className="dot yellow" aria-hidden="true"></span>
        <span>Replay Archives Dashboard</span>
      </div>
      
      <h1 className="placeholder-title">Triage Archives</h1>
      <p className="placeholder-description" style={{ marginBottom: '2.5rem' }}>
        Review previous operational briefs. Launching a replay locks the main dashboard into a static view matching that snapshot configuration.
      </p>

      {isEmpty ? (
        <div className="empty-state-feed glass-panel">
          <div className="empty-graphic" aria-hidden="true">📂</div>
          <h3 className="empty-title">Archive Directory Empty</h3>
          <p className="empty-description">
            No incident triage briefs have been saved to the database yet. Launch ingestion events to generate triage histories.
          </p>
        </div>
      ) : (
        <div className="history-feed" aria-label="Incident triage snapshot history">
          {list.map((snapshot, idx) => {
            const id = snapshot.triage_id || snapshot.id;
            const topTitle = snapshot.top_event_title || snapshot.top_incident_title || 'N/A';
            const topScorePercent = Math.round((snapshot.top_score || 0) * 100);
            
            // Choose severity color for visual hierarchy
            let scoreColorVar = 'var(--state-info)';
            if (snapshot.top_score >= 0.80) {
              scoreColorVar = 'var(--state-critical)';
            } else if (snapshot.top_score >= 0.40) {
              scoreColorVar = 'var(--state-warning)';
            }

            return (
              <div 
                key={id || idx} 
                className="history-card glass-panel"
                role="article"
                aria-label={`Snapshot triaged at ${formatTime(snapshot.generated_at || snapshot.created_at)}`}
              >
                <div className="history-card-body">
                  {/* Top Metadata row */}
                  <div className="history-meta-row">
                    <span className="history-time">{formatTime(snapshot.generated_at || snapshot.created_at)}</span>
                    <span className="history-events-count">
                      {snapshot.total_events || snapshot.total_events_evaluated || 0} telemetry alerts
                    </span>
                    {snapshot.execution_time_ms !== undefined && (
                      <span className="history-latency">
                        SLA: {Math.round(snapshot.execution_time_ms)}ms
                      </span>
                    )}
                  </div>

                  {/* Top Incident Preview */}
                  <h3 className="history-top-event-title">
                    <span className="peak-label">Peak:</span> {topTitle}
                  </h3>

                  {/* Weights readout block */}
                  {snapshot.weights_used && (
                    <div className="history-weights-panel" aria-label="Weights matrix used">
                      {Object.entries(snapshot.weights_used).map(([key, val]) => (
                        <span key={key} className="history-weight-pill">
                          {key[0].toUpperCase()}: {Math.round(val * 100)}%
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Right Replay Button */}
                <div className="history-card-action">
                  <div className="history-peak-score" style={{ color: scoreColorVar }}>
                    {topScorePercent}%
                  </div>
                  <button
                    onClick={() => onReplaySnapshot && onReplaySnapshot(id)}
                    className="replay-action-btn"
                    aria-label={`Launch replay for snapshot ${id}`}
                    type="button"
                  >
                    Replay
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </main>
  )
}

export default TriageHistory
