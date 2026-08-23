import React, { useState } from 'react'

function EventDetail({ event, onClose }) {
  if (!event) return null

  const [isRawExpanded, setIsRawExpanded] = useState(false)

  const {
    event_id = 'N/A',
    id = 'N/A',
    title = 'Unknown Incident',
    source = 'unknown',
    severity = 'info',
    service = 'unknown',
    region = 'global',
    timestamp,
    score = 0,
    priority_score = 0,
    // Gen-AI structured explanation fields
    summary = '',
    why_prioritized = '',
    recommended_action = '',
    provider = 'fallback',
    // Fallbacks if backend flattens them
    explanation = '',
    suggested_action = '',
    explanation_type = 'template',
    details = {}
  } = event

  // Format score as percentage
  const displayScore = Math.round((score || priority_score) * 100)

  // Map severity colors
  let severityColorVar = 'var(--state-info)'
  if (severity === 'critical') {
    severityColorVar = 'var(--state-critical)'
  } else if (severity === 'warning') {
    severityColorVar = 'var(--state-warning)'
  }

  // AI Provider description
  const getProviderName = () => {
    const p = provider || explanation_type
    if (p === 'ollama' || p === 'ai') return 'Ollama Llama3.2'
    if (p === 'gemini') return 'Google Gemini API'
    return 'Rules Fallback Engine'
  }

  // Format timestamp
  const formatFullTime = (timeStr) => {
    if (!timeStr) return 'N/A'
    try {
      const date = new Date(timeStr)
      return date.toLocaleString()
    } catch (e) {
      return timeStr
    }
  }

  return (
    <>
      {/* Backdrop overlay dimming layer */}
      <div 
        className="event-detail-backdrop" 
        onClick={onClose}
        role="presentation"
        aria-hidden="true"
      ></div>

      {/* Detail Slide panel */}
      <div 
        className="event-detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
      >
        {/* Panel Header */}
        <div className="detail-panel-header">
          <h2 id="detail-title" className="detail-panel-title">{title}</h2>
          <button 
            className="detail-close-btn" 
            onClick={onClose}
            aria-label="Close incident brief"
            type="button"
          >
            ✕
          </button>
        </div>

        {/* Panel Scroll Content */}
        <div className="detail-panel-content">
          
          {/* Metadata Grid */}
          <div className="detail-metadata-grid">
            <div className="meta-block">
              <span className="meta-label">Service</span>
              <span className="meta-val">{service}</span>
            </div>
            <div className="meta-block">
              <span className="meta-label">Region</span>
              <span className="meta-val">{region.toUpperCase()}</span>
            </div>
            <div className="meta-block">
              <span className="meta-label">Severity</span>
              <span 
                className={`meta-val severity-badge ${severity}`}
                style={{ color: severityColorVar }}
              >
                {severity.toUpperCase()}
              </span>
            </div>
            <div className="meta-block">
              <span className="meta-label">Source Stream</span>
              <span className="meta-val">{source}</span>
            </div>
            <div className="meta-block span-2">
              <span className="meta-label">Event Timestamp</span>
              <span className="meta-val">{formatFullTime(timestamp)}</span>
            </div>
            <div className="meta-block span-2">
              <span className="meta-label">Telemetry Event ID</span>
              <span className="meta-val monospace-text">{event_id || id}</span>
            </div>
          </div>

          {/* Core priority score visual ring */}
          <div className="detail-score-box glass-panel">
            <div className="score-box-left">
              <span className="score-box-title">Triage Priority Score</span>
              <span className="score-box-description">
                Calculated by multi-factor SRE weighted scoring formulas.
              </span>
            </div>
            <div className="score-box-right">
              <span className="score-badge-circle" style={{ borderColor: severityColorVar }}>
                {displayScore}
              </span>
            </div>
          </div>

          {/* AI Briefing Card Container */}
          <div className="ai-briefing-card glass-panel">
            <div className="ai-brief-header">
              <div className="ai-brief-title">
                <svg className="spark-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707.707M12 7a5 5 0 100 10 5 5 0 000-10z" />
                </svg>
                <span>AI BRIEFING</span>
              </div>
              <span className="ai-provider-badge">
                {getProviderName()}
              </span>
            </div>

            <div className="ai-brief-section">
              <h4 className="brief-section-title">What Happened</h4>
              <p className="brief-section-body">
                {summary || explanation || 'No summary text generated.'}
              </p>
            </div>

            {why_prioritized && (
              <div className="ai-brief-section">
                <h4 className="brief-section-title">Why This Was Prioritized</h4>
                <p className="brief-section-body">
                  {why_prioritized}
                </p>
              </div>
            )}

            <div className="ai-brief-section action-emphasized">
              <h4 className="brief-section-title">Recommended Action</h4>
              <p className="brief-section-body">
                {recommended_action || suggested_action || 'Review event logs and confirm system state.'}
              </p>
            </div>
          </div>

          {/* Collapsible Raw JSON Data Explorer */}
          <div className="raw-explorer-container">
            <button 
              className={`raw-toggle-btn glass-panel ${isRawExpanded ? 'expanded' : ''}`}
              onClick={() => setIsRawExpanded(!isRawExpanded)}
              aria-expanded={isRawExpanded}
              type="button"
            >
              <span>Raw Event Telemetry Payload</span>
              <span className="toggle-arrow">{isRawExpanded ? '▲' : '▼'}</span>
            </button>
            
            {isRawExpanded && (
              <div className="raw-json-panel glass-panel">
                <pre>
                  <code>
                    {JSON.stringify(details, null, 2)}
                  </code>
                </pre>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  )
}

export default EventDetail
