import React from 'react'

function AuditLog({ 
  auditLogs = [], 
  isLoading, 
  error, 
  onRefresh 
}) {

  // Loading skeleton screen
  if (isLoading) {
    return (
      <main className="placeholder-container">
        <div className="placeholder-badge">
          <span className="dot red" aria-hidden="true"></span>
          <span>Loading Telemetry Traces...</span>
        </div>
        <div className="system-status-terminal glass-panel" style={{ width: '100%', maxWidth: '800px', height: '400px', display: 'flex', flexDirection: 'column', gap: '15px', padding: '2rem' }}>
          <div className="skeleton-bar shimmer-bg" style={{ width: '40%', height: '14px' }}></div>
          <div className="skeleton-bar shimmer-bg" style={{ width: '80%', height: '12px' }}></div>
          <div className="skeleton-bar shimmer-bg" style={{ width: '70%', height: '12px' }}></div>
          <div className="skeleton-bar shimmer-bg" style={{ width: '90%', height: '12px' }}></div>
          <div className="skeleton-bar shimmer-bg" style={{ width: '50%', height: '12px' }}></div>
        </div>
      </main>
    )
  }

  // Error screen
  if (error) {
    return (
      <main className="placeholder-container">
        <div className="placeholder-badge">
          <span className="dot red" aria-hidden="true"></span>
          <span>Diagnostic Failures</span>
        </div>
        <div className="empty-state-feed glass-panel" style={{ border: '1px dashed var(--state-critical)', width: '100%', maxWidth: '600px' }}>
          <div className="empty-graphic">📡</div>
          <h3 className="empty-title" style={{ color: 'var(--state-critical)' }}>Trace Stream Disconnected</h3>
          <p className="empty-description" style={{ marginBottom: '1.5rem' }}>
            {error}
          </p>
          <button 
            onClick={onRefresh} 
            className="exit-replay-btn" 
            style={{ background: 'var(--state-critical)' }}
            type="button"
          >
            Retry Diagnostics
          </button>
        </div>
      </main>
    )
  }

  const logs = auditLogs || []
  const totalEntries = logs.length
  
  // Calculate SLA compliance metrics (SLA bound = 5000ms)
  const SLA_TARGET_MS = 5000
  let passedCount = 0
  let maxDuration = 0
  let totalDuration = 0

  logs.forEach(log => {
    const duration = log.duration_ms || log.execution_time_ms || 0
    totalDuration += duration
    if (duration > maxDuration) {
      maxDuration = duration
    }
    if (duration <= SLA_TARGET_MS) {
      passedCount++
    }
  })

  const complianceRate = totalEntries > 0 ? Math.round((passedCount / totalEntries) * 100) : 100
  const avgDuration = totalEntries > 0 ? Math.round(totalDuration / totalEntries) : 0

  // Timestamp formatter helper
  const formatTime = (timeStr) => {
    if (!timeStr) return 'N/A'
    try {
      const date = new Date(timeStr)
      return date.toISOString().replace('T', ' ').substring(0, 19)
    } catch (e) {
      return timeStr
    }
  }

  return (
    <main className="placeholder-container" style={{ minHeight: 'calc(100vh - 160px)', padding: '2rem 1rem' }}>
      
      {/* Title Badge Indicator */}
      <div className="placeholder-badge">
        <span className="dot red" aria-hidden="true"></span>
        <span>SLA Diagnostics Stream</span>
      </div>

      <div className="audit-header-group" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', maxWidth: '800px', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="placeholder-title" style={{ margin: 0, textAlign: 'left' }}>Execution Trace Logs</h1>
          <p className="placeholder-description" style={{ margin: '5px 0 0 0', textAlign: 'left' }}>
            Telemetry stream mapping SRE pipeline run durations and SLA checkpoints.
          </p>
        </div>
        <button 
          onClick={onRefresh} 
          className="replay-action-btn"
          style={{ padding: '0.5rem 1.2rem', fontFamily: 'Outfit', fontWeight: 700 }}
          type="button"
        >
          Refresh Logs
        </button>
      </div>

      {/* SLA Metric Cards Grid */}
      <div className="kpi-grid" style={{ width: '100%', maxWidth: '800px', marginBottom: '2rem' }}>
        
        <div className="kpi-card glass-panel">
          <span className="kpi-label">Trace Entries</span>
          <span className="kpi-value" style={{ color: 'var(--text-primary)' }}>{totalEntries}</span>
          <span className="kpi-desc">Stored logs count</span>
        </div>

        <div className="kpi-card glass-panel">
          <span className="kpi-label">Peak Duration</span>
          <span className="kpi-value" style={{ color: maxDuration > SLA_TARGET_MS ? 'var(--state-critical)' : 'var(--accent-cyan)' }}>
            {Math.round(maxDuration)}ms
          </span>
          <span className="kpi-desc">Max processing time</span>
        </div>

        <div className="kpi-card glass-panel">
          <span className="kpi-label">SLA Threshold</span>
          <span className="kpi-value" style={{ color: 'var(--text-secondary)' }}>{SLA_TARGET_MS}ms</span>
          <span className="kpi-desc">SLA target limit</span>
        </div>

        <div className="kpi-card glass-panel">
          <span className="kpi-label">SLA Compliance</span>
          <span className="kpi-value" style={{ color: complianceRate >= 90 ? 'var(--state-success)' : 'var(--state-warning)' }}>
            {complianceRate}%
          </span>
          <span className="kpi-desc">SLA pass rate</span>
        </div>

      </div>

      {/* Central terminal block */}
      {totalEntries === 0 ? (
        <div className="empty-state-feed glass-panel" style={{ width: '100%', maxWidth: '800px' }}>
          <div className="empty-graphic" aria-hidden="true">📜</div>
          <h3 className="empty-title">Console Trace Log Empty</h3>
          <p className="empty-description">
            No pipeline action entries have been saved to the logging database yet.
          </p>
        </div>
      ) : (
        <div className="system-status-terminal glass-panel" style={{ width: '100%', maxWidth: '800px', textAlign: 'left' }}>
          <div className="terminal-header">
            <span className="terminal-title">aurabrief_triage_audit.sys</span>
            <div className="terminal-actions">
              <span className="dot green" style={{ width: '10px', height: '10px' }} aria-hidden="true"></span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>LIVE STREAMING</span>
            </div>
          </div>
          
          <div className="terminal-body" style={{ maxHeight: '500px', overflowY: 'auto', padding: '1.2rem', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem', lineSpacing: '1.5' }}>
            {logs.map((log) => {
              const dur = log.duration_ms || log.execution_time_ms || 0
              const isBreached = dur > SLA_TARGET_MS
              
              return (
                <div key={log.id} style={{ marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '1rem' }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>
                    [{formatTime(log.timestamp)}] <span style={{ color: 'var(--accent-indigo)', fontWeight: '700' }}>{log.action || 'PIPELINE_RUN'}</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    ├─ STATUS      <span style={{ color: isBreached ? 'var(--state-critical)' : 'var(--state-success)', fontWeight: '700' }}>
                      {isBreached ? 'BREACH' : 'SUCCESS'}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    ├─ STEP        <span style={{ color: 'var(--accent-cyan)' }}>{log.step || 'general'}</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    ├─ DURATION    <span style={{ color: isBreached ? 'var(--state-critical)' : 'var(--text-primary)' }}>{Math.round(dur)}ms</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    ├─ SLA         <span style={{ color: isBreached ? 'var(--state-critical)' : 'var(--state-success)' }}>
                      {SLA_TARGET_MS}ms ({isBreached ? 'BREACH' : 'PASS'})
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    ├─ ACTOR       <span>{log.actor || 'system'}</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
                    └─ LOG MSG     <span style={{ color: 'var(--text-primary)' }}>{log.message}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </main>
  )
}

export default AuditLog
