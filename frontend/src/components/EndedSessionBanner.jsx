import React from 'react';
import { Link } from 'react-router-dom';
import { useSession } from '../hooks/useSession';
import { formatDuration } from '../utils/date.utils';

export const EndedSessionBanner = () => {
  const { recentEndedSession, clearEndedNotification } = useSession();

  if (!recentEndedSession) return null;

  return (
    <div className="ended-session-card">
      <div className="ended-session-badge">
        <span className="ended-icon">🎉</span> SESSION COMPLETED
      </div>

      <div className="ended-session-body">
        <div className="ended-session-meta">
          <h3 className="ended-game-title">{recentEndedSession.gameName || 'Game Session'}</h3>
          <p className="ended-duration-text">
            Duration: <strong>{formatDuration(recentEndedSession.duration)}</strong>
            {recentEndedSession.platform && ` • ${recentEndedSession.platform}`}
          </p>
          <p className="ended-subtext">Your gaming session telemetry has been safely recorded.</p>
        </div>

        <div className="ended-session-actions">
          <Link to="/sessions" className="btn-primary" onClick={clearEndedNotification}>
            View Session History →
          </Link>
          <button className="btn-dismiss" onClick={clearEndedNotification} aria-label="Dismiss banner">
            ✕
          </button>
        </div>
      </div>
    </div>
  );
};

export default EndedSessionBanner;
