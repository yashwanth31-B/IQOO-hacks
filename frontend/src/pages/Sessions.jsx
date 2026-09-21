import React, { useState } from 'react';
import { useSession } from '../hooks/useSession';
import ActiveSessionCard from '../components/ActiveSessionCard';
import StartSessionModal from '../components/StartSessionModal';
import EndedSessionBanner from '../components/EndedSessionBanner';
import SessionHistoryList from '../components/SessionHistoryList';
import HealthBadge from '../components/HealthBadge';

export const Sessions = () => {
  const { activeSession, loadingActive, fetchActiveSession } = useSession();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const handleSessionStarted = () => {
    fetchActiveSession();
    setHistoryRefreshKey((prev) => prev + 1);
  };

  const handleSessionEnded = () => {
    setHistoryRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Gaming Sessions</h1>
          <p className="page-subtitle">
            Manage live gaming telemetry, record match performance, and browse your gaming history.
          </p>
        </div>
        <div className="page-actions">
          {!activeSession && !loadingActive && (
            <button
              className="btn-primary"
              onClick={() => setIsModalOpen(true)}
            >
              🎮 Start Session
            </button>
          )}
          <HealthBadge />
        </div>
      </div>

      {/* Completion Banner if a session just ended */}
      <EndedSessionBanner />

      {/* Active Session Section (if any is live) */}
      {activeSession && (
        <div className="active-session-section mb-4">
          <ActiveSessionCard onSessionEnded={handleSessionEnded} />
        </div>
      )}

      {/* Historical Sessions List */}
      <div className="panel-card">
        <SessionHistoryList
          refreshTrigger={historyRefreshKey}
          onStartSessionClick={() => setIsModalOpen(true)}
        />
      </div>

      {/* Start Session Modal */}
      <StartSessionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSessionStarted={handleSessionStarted}
      />
    </div>
  );
};

export default Sessions;
