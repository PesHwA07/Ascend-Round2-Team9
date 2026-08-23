import { useState, useCallback } from 'react'

const API_TIMEOUT_MS = 4000; // 4-second timeout limit

// Helper to wrap fetch with a timeout using AbortController
async function fetchWithTimeout(resource, options = {}) {
  const { timeout = API_TIMEOUT_MS } = options;
  
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(resource, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Common request handler
  const request = useCallback(async (url, options = {}) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithTimeout(url, options);
      
      // Handle HTTP status errors (e.g. 404, 500, 422)
      if (!response.ok) {
        let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
        try {
          // Attempt to extract FastAPI validation error message details
          const errData = await response.json();
          if (errData && errData.detail) {
            if (Array.isArray(errData.detail)) {
              errorMsg = errData.detail.map(d => `${d.loc.join('.')}: ${d.msg}`).join(', ');
            } else {
              errorMsg = errData.detail;
            }
          }
        } catch (_) {
          // If response body is not JSON, fallback to standard status message
        }
        throw new Error(errorMsg);
      }
      
      const data = await response.json();
      setLoading(false);
      return data;
    } catch (err) {
      setLoading(false);
      let friendlyMsg = err.message;
      if (err.name === 'AbortError') {
        friendlyMsg = 'Connection timeout. Telemetry server did not respond.';
      } else if (err.message.includes('Failed to fetch') || err.message.includes('Load failed')) {
        friendlyMsg = 'Network connection failure. Telemetry server is unreachable.';
      }
      setError(friendlyMsg);
      throw new Error(friendlyMsg);
    }
  }, []);

  // 1. GET /api/health - Heartbeat check
  const getHealth = useCallback(async () => {
    return request('/api/health');
  }, [request]);

  // 2. GET /api/triage/current - Retrieves active incident list
  const getCurrentTriage = useCallback(async (params = {}) => {
    const query = new URLSearchParams();
    if (params.limit) query.append('limit', params.limit);
    if (params.min_score !== undefined) query.append('min_score', params.min_score);
    if (params.source) query.append('source', params.source);
    
    const queryString = query.toString();
    const url = `/api/triage/current${queryString ? '?' + queryString : ''}`;
    return request(url);
  }, [request]);

  // 3. GET /api/triage/history - Retrieves past triage run lists
  const getHistory = useCallback(async (limit = 20) => {
    return request(`/api/triage/history?limit=${limit}`);
  }, [request]);

  // 4. GET /api/triage/history/{triage_id} - Retrieves full details for a historic run
  const getHistoryDetails = useCallback(async (triageId) => {
    return request(`/api/triage/history/${triageId}`);
  }, [request]);

  // 5. GET /api/triage/replay/{snapshot_id} - Replays specific snapshots
  const replaySnapshot = useCallback(async (snapshotId) => {
    return request(`/api/triage/replay/${snapshotId}`);
  }, [request]);

  // 6. POST /api/feedback - Updates active weights configurations
  const postFeedback = useCallback(async (weights) => {
    return request('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ weights })
    });
  }, [request]);

  // 7. GET /api/audit-log - Retrieves background traces
  const getAuditLog = useCallback(async (limit = 50) => {
    return request(`/api/audit-log?limit=${limit}`);
  }, [request]);

  return {
    loading,
    error,
    getHealth,
    getCurrentTriage,
    getHistory,
    getHistoryDetails,
    replaySnapshot,
    postFeedback,
    getAuditLog
  };
}
