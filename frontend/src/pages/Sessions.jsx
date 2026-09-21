import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useSession } from '../hooks/useSession';
import ActiveSessionCard from '../components/ActiveSessionCard';
import StartSessionModal from '../components/StartSessionModal';
import EndedSessionBanner from '../components/EndedSessionBanner';
import HealthBadge from '../components/HealthBadge';

/**
 * CYBER HUD — "NOW"
 * Live Gaming Cockpit displaying strictly current/active session telemetry,
 * real-time timer, in-game performance rating, and tactical match controls.
 */
export const Sessions = () => {
  const { activeSession, loadingActive, fetchActiveSession } = useSession();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleSessionStarted = () => {
    fetchActiveSession();
  };

  const handleSessionEnded = () => {
    fetchActiveSession();
  };

  return (
    <div className="page-container">
      {/* 1. Header: CYBER HUD ("NOW") */}
      <div className="page-header">
        <div>
          <div className="header-eyebrow">
            <span className="badge-connected">● LIVE GAMING COCKPIT</span>
            <span className="badge-mvp">TIER 1 · "NOW"</span>
          </div>
          <h1 className="page-title">Cyber HUD</h1>
          <p className="page-subtitle">
            Real-time telemetry, active match clock, live performance rating, and tactical session controls.
          </p>
        </div>
        <div className="page-actions">
          {!activeSession && !loadingActive && (
            <button
              className="btn-primary"
              onClick={() => setIsModalOpen(true)}
            >
              🎮 Start Live Session
            </button>
          )}
          <HealthBadge />
        </div>
      </div>

      {/* Completion Banner if a session just ended */}
      <EndedSessionBanner />

      {/* 2. Active Session Cockpit (Live Telemetry) */}
      {activeSession ? (
        <div className="active-session-section mb-4">
          <ActiveSessionCard onSessionEnded={handleSessionEnded} />
        </div>
      ) : (
        /* Standby Cockpit when Idle */
        !loadingActive && (
          <div className="no-active-session-card mb-4" style={{ border: '1px dashed rgba(56, 189, 248, 0.4)' }}>
            <div className="no-session-content">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span className="no-session-badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
                  HUD STATUS: STANDBY
                </span>
                <span className="badge-mvp">TELEMETRY READY</span>
              </div>
              <h2 className="no-session-title">Cyber HUD Ready for Deployment</h2>
              <p className="no-session-desc">
                No active gaming session is currently broadcasting. Start a match session to activate real-time telemetry, live duration tracking, and instant tactical in-game ratings.
              </p>
              <button
                className="btn-primary btn-large mt-3"
                onClick={() => setIsModalOpen(true)}
              >
                🎮 Start Live Session Now
              </button>
            </div>
          </div>
        )
      )}

      {/* 3. Bridge to Gaming Second Brain ("BEFORE") */}
      <div className="panel-card" style={{ border: '1px solid rgba(139, 92, 246, 0.3)', background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.06) 0%, var(--bg-card) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="logo-symbol">🧠</span>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Historical Knowledge Vault · "BEFORE"
              </span>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Looking for past match archives & long-term memory?
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.25rem', maxWidth: '650px' }}>
              The Cyber HUD keeps focus on your <strong>live match right now</strong>. All completed match histories, cognitive memory tiers (Episodic, Semantic, Procedural), and peak records live in your <strong>Gaming Second Brain</strong>.
            </p>
          </div>
          <Link
            to="/memories"
            className="btn-secondary"
            style={{ padding: '0.75rem 1.25rem', borderColor: 'rgba(139, 92, 246, 0.5)', color: '#c4b5fd' }}
          >
            Explore Second Brain ("BEFORE") →
          </Link>
        </div>
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
