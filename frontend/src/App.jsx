import React, { useState } from 'react'
import Header from './components/Header.jsx'
import './index.css'

function App() {
  // 1. Core state variables defined by FRONTEND_PRD.md
  const [activeTab, setActiveTab] = useState('brief')
  const [triageData, setTriageData] = useState([])
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

      {/* Dashboard Main Workspace Placeholder */}
      <main className="placeholder-container">
        <div className="placeholder-badge">
          <span className="dot green" aria-hidden="true"></span>
          <span>AuraBrief 95 Core Shell</span>
        </div>
        
        <h1 className="placeholder-title">AI Operations Briefing</h1>
        <p className="placeholder-description">
          A multi-region SaaS event triage dashboard. The interface scores, prioritizes, and explains production incidents in real time.
        </p>

        {/* Premium Diagnostic Monospace Terminal Shell */}
        <div className="system-status-terminal glass-panel" aria-label="Console diagnostic terminal">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span className="dot red" aria-hidden="true"></span>
              <span className="dot yellow" aria-hidden="true"></span>
              <span className="dot green" aria-hidden="true"></span>
            </div>
            <span className="terminal-title">aurabrief_triage_core.sys</span>
          </div>

          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true">&gt;</span>
            <span>initializing telemetry listeners...</span>
          </div>
          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true">&gt;</span>
            <span>active weight matrix loaded:</span>
          </div>
          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true"></span>
            <span className="terminal-value-info">
              {JSON.stringify(activeWeights, null, 2)}
            </span>
          </div>
          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true">&gt;</span>
            <span>database connection state: <span className="terminal-value-success">CONNECTED</span></span>
          </div>
          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true">&gt;</span>
            <span>active interface: <span className="terminal-value-info">{activeTab.toUpperCase()} PANEL</span></span>
          </div>
          <div className="terminal-line">
            <span className="terminal-prompt" aria-hidden="true">&gt;</span>
            <span>live triage interface coming online<span className="terminal-cursor" aria-hidden="true"></span></span>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
