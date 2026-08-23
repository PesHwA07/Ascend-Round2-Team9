import React, { useState, useEffect } from 'react'

function FeedbackPanel({ currentWeights, onUpdateWeights, isLoading, disabled }) {
  // Local state to track sliders in integer percent (0 to 100)
  const [tempWeights, setTempWeights] = useState({
    severity: 30,
    frequency: 20,
    recency: 15,
    anomaly: 20,
    business_impact: 15
  })
  
  const [submitError, setSubmitError] = useState('')
  const [submitSuccess, setSubmitSuccess] = useState(false)

  // Sync temp weights when parent currentWeights change (e.g. on startup load)
  useEffect(() => {
    if (currentWeights) {
      setTempWeights({
        severity: Math.round((currentWeights.severity || 0) * 100),
        frequency: Math.round((currentWeights.frequency || 0) * 100),
        recency: Math.round((currentWeights.recency || 0) * 100),
        anomaly: Math.round((currentWeights.anomaly || 0) * 100),
        business_impact: Math.round((currentWeights.business_impact || 0) * 100)
      })
    }
  }, [currentWeights])

  // Calculate sum total percentage
  const totalPercentage = 
    tempWeights.severity + 
    tempWeights.frequency + 
    tempWeights.recency + 
    tempWeights.anomaly + 
    tempWeights.business_impact;

  const isBudgetBalanced = totalPercentage === 100;
  const isBudgetOver = totalPercentage > 100;

  // Handle slider modifications
  const handleSliderChange = (factor, value) => {
    setTempWeights(prev => ({
      ...prev,
      [factor]: parseInt(value) || 0
    }));
    // Clear any previous submit states
    setSubmitError('');
    setSubmitSuccess(false);
  }

  // Handle weight application POST request
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isBudgetBalanced || disabled) return;

    setSubmitError('');
    setSubmitSuccess(false);

    // Map integer percentages back to decimal values (e.g. 30 -> 0.30)
    const decimalWeights = {
      severity: tempWeights.severity / 100,
      frequency: tempWeights.frequency / 100,
      recency: tempWeights.recency / 100,
      anomaly: tempWeights.anomaly / 100,
      business_impact: tempWeights.business_impact / 100
    };

    try {
      await onUpdateWeights(decimalWeights);
      setSubmitSuccess(true);
      // Automatically hide success notification after 3 seconds
      setTimeout(() => setSubmitSuccess(false), 3000);
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit weights update.');
    }
  }

  return (
    <div className="feedback-panel glass-panel" aria-label="Incident scoring configuration">
      <div className="feedback-header-area">
        <h3 className="feedback-title">Triage Weights Configuration</h3>
        {disabled ? (
          <p className="feedback-subtitle" style={{ color: 'var(--state-warning)' }}>
            Sliders are locked while inspecting static historical snapshots in Replay Mode.
          </p>
        ) : (
          <p className="feedback-subtitle">
            Adjust the relative importance of operational factors. The total budget must equal exactly 100%.
          </p>
        )}
      </div>

      <form onSubmit={handleSubmit} className="feedback-form">
        
        {/* Slider Controls Block */}
        <div className="sliders-stack">
          {[
            { id: 'severity', label: 'Severity Weight', desc: 'Alert threat level' },
            { id: 'frequency', label: 'Frequency Weight', desc: 'Alert recurrence count' },
            { id: 'recency', label: 'Recency Weight', desc: 'Time-decay score' },
            { id: 'anomaly', label: 'Anomaly Weight', desc: 'Baseline deviation' },
            { id: 'business_impact', label: 'Business Impact Weight', desc: 'Service tier priority' }
          ].map(slider => (
            <div key={slider.id} className="slider-control-group">
              <div className="slider-labels-row">
                <label htmlFor={`slider-${slider.id}`} className="slider-main-label">
                  {slider.label}
                  <span className="slider-desc-label"> ({slider.desc})</span>
                </label>
                <span className="slider-percentage-value">
                  {tempWeights[slider.id]}%
                </span>
              </div>
              <input
                id={`slider-${slider.id}`}
                type="range"
                min="0"
                max="100"
                step="1"
                value={tempWeights[slider.id]}
                onChange={(e) => handleSliderChange(slider.id, e.target.value)}
                disabled={isLoading || disabled}
                className="weight-range-input"
              />
            </div>
          ))}
        </div>

        {/* Budget Status Tracker Ring */}
        <div className="budget-status-row">
          <div className="budget-status-left">
            <span className="budget-status-title">Weights Total Budget</span>
            <span className={`budget-status-indicator ${isBudgetBalanced ? 'balanced' : isBudgetOver ? 'over' : 'under'}`}>
              {isBudgetBalanced ? '✓ Balanced' : isBudgetOver ? '⚠ Over Budget' : '⚠ Under Budget'}
            </span>
          </div>
          <div className={`budget-total-pill ${isBudgetBalanced ? 'balanced' : 'unbalanced'}`}>
            {totalPercentage}/100 %
          </div>
        </div>

        {/* Submit Actions, Error, and Success messages */}
        <div className="feedback-actions-row">
          {submitError && (
            <div className="feedback-error-banner" role="alert">
              <span>⚠ {submitError}</span>
            </div>
          )}
          
          {submitSuccess && (
            <div className="feedback-success-banner" role="status">
              <span>✓ Weights applied successfully.</span>
            </div>
          )}

          <button
            type="submit"
            disabled={!isBudgetBalanced || isLoading || disabled}
            className="apply-weights-btn"
          >
            {disabled ? 'Replay Mode Locked' : isLoading ? 'Recalculating...' : 'Apply Custom Weights'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default FeedbackPanel
