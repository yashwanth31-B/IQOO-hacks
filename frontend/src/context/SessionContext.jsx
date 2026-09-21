import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';

const SessionContext = createContext(null);

export const SessionProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [activeSession, setActiveSession] = useState(null);
  const [loadingActive, setLoadingActive] = useState(true);
  const [sessionError, setSessionError] = useState(null);
  const [recentEndedSession, setRecentEndedSession] = useState(null);

  /**
   * Fetch currently active gaming session from backend
   */
  const fetchActiveSession = useCallback(async () => {
    if (!isAuthenticated) {
      setActiveSession(null);
      setLoadingActive(false);
      return null;
    }

    setLoadingActive(true);
    setSessionError(null);
    try {
      const response = await api.get('/sessions/active');
      if (response && response.success) {
        setActiveSession(response.session || null);
        return response.session || null;
      }
      return null;
    } catch (err) {
      setSessionError(err.message || 'Failed to check active gaming session');
      return null;
    } finally {
      setLoadingActive(false);
    }
  }, [isAuthenticated]);

  // Load active session whenever user authentication status changes
  useEffect(() => {
    fetchActiveSession();
  }, [fetchActiveSession]);

  /**
   * Start a new gaming session
   * @param {Object} param0 
   * @returns {Promise<Object>}
   */
  const startSession = async ({ gameId, score, performance, notes }) => {
    setSessionError(null);
    try {
      const payload = { gameId };
      if (score !== undefined && score !== null && score !== '') {
        payload.score = Number(score);
      }
      if (performance && performance.trim()) {
        payload.performance = performance.trim();
      }
      if (notes && notes.trim()) {
        payload.notes = notes.trim();
      }

      const response = await api.post('/sessions', payload);
      if (response && response.success && response.session) {
        setActiveSession(response.session);
        setRecentEndedSession(null);
        return response.session;
      }
      throw new Error(response.message || 'Failed to start gaming session');
    } catch (err) {
      setSessionError(err.message);
      throw err;
    }
  };

  /**
   * Update active gaming session fields (score, performance, notes)
   * @param {Object} updates 
   * @returns {Promise<Object>}
   */
  const updateSession = async (updates) => {
    if (!activeSession) {
      throw new Error('No active session to update');
    }

    setSessionError(null);
    try {
      const response = await api.patch(`/sessions/${activeSession.id}`, updates);
      if (response && response.success && response.session) {
        setActiveSession((prev) => ({
          ...prev,
          ...response.session
        }));
        return response.session;
      }
      throw new Error(response.message || 'Failed to update session');
    } catch (err) {
      setSessionError(err.message);
      throw err;
    }
  };

  /**
   * End currently active gaming session
   * @returns {Promise<Object>}
   */
  const endActiveSession = async () => {
    if (!activeSession) {
      throw new Error('No active session to end');
    }

    setSessionError(null);
    try {
      const response = await api.post(`/sessions/${activeSession.id}/end`);
      if (response && response.success && response.session) {
        const ended = response.session;
        setRecentEndedSession(ended);
        setActiveSession(null);
        return ended;
      }
      throw new Error(response.message || 'Failed to end session');
    } catch (err) {
      setSessionError(err.message);
      throw err;
    }
  };

  /**
   * Dismiss recent ended session banner
   */
  const clearEndedNotification = () => {
    setRecentEndedSession(null);
  };

  const value = {
    activeSession,
    loadingActive,
    sessionError,
    recentEndedSession,
    fetchActiveSession,
    startSession,
    updateSession,
    endActiveSession,
    clearEndedNotification
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

export default SessionContext;
