import React from 'react'

function Header({ activeTab, setActiveTab, connectionStatus }) {
  return (
    <header className="header-nav" aria-label="AuraBrief Navigation Header">
      {/* LEFT: Branding Logo with Glowing Dot */}
      <a 
        href="#/" 
        className="brand-container" 
        onClick={(e) => { 
          e.preventDefault(); 
          setActiveTab('brief'); 
        }}
        aria-label="AuraBrief 95 home"
      >
        <div className="brand-ring" aria-hidden="true"></div>
        <div className="brand-title-group">
          <span className="brand-title">AuraBrief 95</span>
          <span className="brand-subtitle">AI Ops Console</span>
        </div>
      </a>

      {/* CENTER: Navigation Tabs (Briefing, History, Audit Logs) */}
      <nav className="tabs-container" aria-label="Operations view select">
        <button
          className={`tab-button ${activeTab === 'brief' ? 'active' : ''}`}
          onClick={() => setActiveTab('brief')}
          aria-current={activeTab === 'brief' ? 'page' : undefined}
          type="button"
        >
          BRIEFING
        </button>
        <button
          className={`tab-button ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
          aria-current={activeTab === 'history' ? 'page' : undefined}
          type="button"
        >
          HISTORY
        </button>
        <button
          className={`tab-button ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
          aria-current={activeTab === 'audit' ? 'page' : undefined}
          type="button"
        >
          AUDIT LOGS
        </button>
      </nav>

      {/* RIGHT: Dynamic Backend Status Beacon */}
      <div className="health-status-container">
        <div className="status-badge" aria-label="System status connection badge">
          <span 
            className={`status-beacon ${connectionStatus === 'online' ? 'online' : connectionStatus === 'demo' ? 'warning' : 'offline'}`}
            role="presentation"
          ></span>
          <span 
            className={`status-text ${connectionStatus === 'online' ? 'online' : connectionStatus === 'demo' ? 'warning' : 'offline'}`} 
            aria-live="polite"
          >
            {connectionStatus === 'online' ? 'SYSTEM ONLINE' : connectionStatus === 'demo' ? 'DEMO DATA' : 'OFFLINE — RETRYING'}
          </span>
        </div>
      </div>
    </header>
  )
}

export default Header
