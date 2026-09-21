import React, { useState, useEffect } from 'react';
import { useSession } from '../hooks/useSession';
import { useSessionTimer } from '../hooks/useSessionTimer';
import { formatSessionDate } from '../utils/date.utils';
import ErrorMessage from './ErrorMessage';

export const ActiveSessionCard = ({ onSessionEnded }) => {
  const { activeSession, updateSession, endActiveSession } = useSession();

  // Real live elapsed timer calculated strictly from backend startedAt
  const { formattedTimer } = useSessionTimer(activeSession?.startedAt);

  // Form controls for Score, Performance, Notes
  const [score, setScore] = useState('');
  const [performance, setPerformance] = useState('');
  const [notes, setNotes] = useState('');

  const [saving, setSaving] = useState(false);
  const [ending, setEnding] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [actionError, setActionError] = useState('');

  // Synchronize local form state with activeSession whenever it loads/changes
  useEffect(() => {
    if (activeSession) {
      setScore(activeSession.score !== null && activeSession.score !== undefined ? String(activeSession.score) : '');
      setPerformance(activeSession.performance || '');
      setNotes(activeSession.notes || '');
      setActionError('');
      setSaveSuccess(false);
    }
  }, [activeSession]);

  if (!activeSession) return null;

  const handleSaveUpdate = async (e) => {
    e.preventDefault();
    setActionError('');
    setSaveSuccess(false);
    setSaving(true);

    try {
      const updates = {};
      if (score !== '') {
        const numScore = Number(score);
        if (isNaN(numScore)) {
          setActionError('Score must be a valid number');
          setSaving(false);
          return;
        }
        updates.score = numScore;
      } else {
        updates.score = null;
      }

      updates.performance = performance.trim() || null;
      updates.notes = notes.trim() || null;

      await updateSession(updates);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setActionError(err.message || 'Failed to update session');
    } finally {
      setSaving(false);
    }
  };

  const handleEndSession = async () => {
    setActionError('');
    setEnding(true);
    try {
      await endActiveSession();
      if (onSessionEnded) onSessionEnded();
    } catch (err) {
      setActionError(err.message || 'Failed to end session');
    } finally {
      setEnding(false);
    }
  };

  return (
    <div className="active-session-card">
      <div className="active-session-header">
        <div className="active-game-info">
          <span className="live-status-pill">
            <span className="live-dot-pulse"></span> LIVE
          </span>
          <div>
            <h2 className="active-game-title">{activeSession.gameName || 'Active Game'}</h2>
            <span className="active-game-meta">
              {activeSession.platform || 'PC'} • Started {formatSessionDate(activeSession.startedAt)}
            </span>
          </div>
        </div>

        <div className="active-timer-box">
          <span className="timer-label">SESSION ELAPSED</span>
          <span className="timer-clock">{formattedTimer}</span>
        </div>
      </div>

      <ErrorMessage message={actionError} />

      {saveSuccess && (
        <div className="success-banner">
          ✓ Session details updated successfully!
        </div>
      )}

      {/* Live Session Telemetry Form */}
      <form className="active-session-form" onSubmit={handleSaveUpdate}>
        <div className="session-inputs-row">
          <div className="form-group flex-1">
            <label htmlFor="active-score">Current Score / Points</label>
            <input
              id="active-score"
              type="number"
              placeholder="e.g. 1550"
              value={score}
              onChange={(e) => setScore(e.target.value)}
              disabled={saving || ending}
            />
          </div>

          <div className="form-group flex-1">
            <label htmlFor="active-perf">Performance Rating</label>
            <select
              id="active-perf"
              value={performance}
              onChange={(e) => setPerformance(e.target.value)}
              disabled={saving || ending}
            >
              <option value="">Select rating...</option>
              <option value="Excellent">Excellent 🔥</option>
              <option value="Good">Good 👍</option>
              <option value="Average">Average ⚖️</option>
              <option value="Tough">Tough / Rough 🛑</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="active-notes">Gameplay Notes & Tactics</label>
          <textarea
            id="active-notes"
            rows="2"
            placeholder="Record clutch rounds, enemy tactics, or notes for the AI Copilot..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={saving || ending}
          />
        </div>

        <div className="active-session-actions">
          <button
            type="submit"
            className="btn-secondary"
            disabled={saving || ending}
          >
            {saving ? <span className="btn-spinner"></span> : '💾 Save Session Update'}
          </button>

          <button
            type="button"
            className="btn-danger"
            onClick={handleEndSession}
            disabled={saving || ending}
          >
            {ending ? <span className="btn-spinner"></span> : '⏹ End Session'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ActiveSessionCard;
