import React from 'react'

function EventCard({ event, onSelect }) {
  if (!event) return null

  const {
    title = 'Unknown Incident',
    source = 'unknown',
    severity = 'info',
    service = 'unknown',
    region = 'global',
    timestamp,
    score = 0,
    explanation = '',
    suggested_action = '',
  } = event

  // Safely parse structured vs flat explanations to avoid JSX object rendering crashes
  let briefText = ''
  let actionText = ''

  if (typeof explanation === 'object' && explanation !== null) {
    briefText = explanation.summary || ''
    actionText = explanation.recommended_action || suggested_action || ''
  } else {
    briefText = explanation || ''
    actionText = suggested_action || ''
  }

  // Format score as percentage (e.g. 0.92 -> 92)
  const scorePercent = Math.round(score * 100)
  
  // Choose stroke color variables based on score value
  let scoreColorVar = 'var(--state-info)'
  if (score >= 0.80) {
    scoreColorVar = 'var(--state-critical)'
  } else if (score >= 0.40) {
    scoreColorVar = 'var(--state-warning)'
  }

  // Calculate SVG dash offset
  const radius = 20
  const circumference = 2 * Math.PI * radius // ~125.66
  const strokeDashoffset = circumference - (score * circumference)

  // Format timestamp (human-readable time)
  const formatTime = (timeStr) => {
    if (!timeStr) return 'just now'
    try {
      const date = new Date(timeStr)
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch (e) {
      return 'recent'
    }
  }

  return (
    <div 
      className={`event-card glass-panel severity-${severity}`}
      onClick={() => onSelect && onSelect(event)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect && onSelect(event)
        }
      }}
      aria-label={`Incident on ${service} in ${region}, Priority score ${scorePercent} percent`}
    >
      {/* Left indicator strip for severity */}
      <div className={`severity-strip ${severity}`} role="presentation"></div>

      {/* Content Body */}
      <div className="event-card-body">
        <div className="event-card-meta">
          <span className="meta-tag source-tag">{source}</span>
          <span className="meta-divider" aria-hidden="true">•</span>
          <span className="meta-tag service-tag">{service}</span>
          <span className="meta-divider" aria-hidden="true">•</span>
          <span className="meta-tag region-tag">{region.toUpperCase()}</span>
          <span className="meta-divider" aria-hidden="true">•</span>
          <span className="meta-time">{formatTime(timestamp)}</span>
        </div>

        <h3 className="event-card-title">{title}</h3>
        
        {briefText && (
          <p className="event-card-excerpt">
            <span className="excerpt-label">AI Brief:</span> {briefText}
          </p>
        )}

        {actionText && (
          <div className="event-card-action-preview">
            <span className="action-label">Action:</span> {actionText}
          </div>
        )}
      </div>

      {/* Right Score Gauge */}
      <div className="event-card-gauge-container">
        <svg className="score-ring" width="54" height="54" aria-hidden="true">
          <circle 
            cx="27" 
            cy="27" 
            r={radius} 
            stroke="rgba(255, 255, 255, 0.05)" 
            strokeWidth="3" 
            fill="transparent" 
          />
          <circle 
            cx="27" 
            cy="27" 
            r={radius} 
            stroke={scoreColorVar} 
            strokeWidth="3" 
            fill="transparent" 
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 27 27)" 
          />
          <text 
            x="27" 
            y="27" 
            textAnchor="middle" 
            dy=".3em" 
            fontFamily="Outfit" 
            fontSize="12" 
            fontWeight="700" 
            fill="var(--text-primary)"
          >
            {scorePercent}
          </text>
        </svg>
        <button 
          className="view-brief-btn"
          type="button"
          tabIndex={-1} /* outer card div is the main keyboard target */
        >
          View Brief
        </button>
      </div>
    </div>
  )
}

export default EventCard
