import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useSession } from '../hooks/useSession';
import api from '../services/api';
import { formatDuration } from '../utils/date.utils';

import ActiveSessionCard from '../components/ActiveSessionCard';
import StartSessionModal from '../components/StartSessionModal';
import EndedSessionBanner from '../components/EndedSessionBanner';
import HealthBadge from '../components/HealthBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export const Dashboard = () => {
  const { user } = useAuth();
  const { activeSession, loadingActive, fetchActiveSession } = useSession();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sessionStats, setSessionStats] = useState({
    totalSessions: 0,
    totalDurationSeconds: 0,
    loading: true
  });

  // Calculate real metrics from backend session records
  const loadStats = useCallback(async () => {
    try {
      // Fetch up to 100 recent sessions to compute total time & count
      const response = await api.get('/sessions?page=1&limit=100');
      if (response && response.success) {
        const list = response.sessions || [];
        const totalDuration = list.reduce((acc, curr) => {
          return acc + (Number(curr.duration) || 0);
        }, 0);

        setSessionStats({
          totalSessions: response.pagination?.total ?? list.length,
          totalDurationSeconds: totalDuration,
          loading: false
        });
      }
    } catch {
      setSessionStats((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats, activeSession]);

  const handleSessionStarted = () => {
    fetchActiveSession();
    loadStats();
  };

  const handleSessionEnded = () => {
    loadStats();
  };

  return (
    <div className="page-container">
      {/* 3. Dashboard Header */}
      <div className="page-header">
        <div>
          <div className="header-eyebrow">
            <span className="logo-symbol">⚔️</span> AI GAMING COPILOT
          </div>
          <h1 className="page-title">
            {user?.name ? `Welcome back, ${user.name}` : 'Welcome, Player'}
          </h1>
          <p className="page-subtitle">Play smarter. Remember better. Improve faster.</p>
        </div>
        <div className="page-actions">
          <HealthBadge />
        </div>
      </div>

      {/* Completion Banner if a session just ended */}
      <EndedSessionBanner />

      {/* 4. Current Gaming Session Section */}
      <div className="dashboard-section">
        {loadingActive ? (
          <div className="panel-card">
            <LoadingSpinner message="Checking active gaming session..." />
          </div>
        ) : activeSession ? (
          <ActiveSessionCard onSessionEnded={handleSessionEnded} />
        ) : (
          <div className="no-active-session-card">
            <div className="no-session-content">
              <span className="no-session-badge">NO ACTIVE SESSION</span>
              <h2 className="no-session-title">Ready to play?</h2>
              <p className="no-session-desc">
                Start a gaming session and let your Copilot keep track of your journey, tactical
                discoveries, and performance score.
              </p>
              <button
                className="btn-primary btn-large mt-3"
                onClick={() => setIsModalOpen(true)}
              >
                🎮 Start Gaming Session
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 10. Dashboard Overview Cards (Real Data Only) */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Current Status</span>
            <span className="metric-icon">{activeSession ? '🔥' : '💤'}</span>
          </div>
          <div className="metric-value">
            {activeSession ? (
              <span className="text-live">PLAYING</span>
            ) : (
              <span className="text-secondary">IDLE</span>
            )}
          </div>
          <p className="metric-desc">
            {activeSession
              ? `Currently in: ${activeSession.gameName || 'Live Session'}`
              : 'Waiting for next gaming sprint'}
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Total Sessions</span>
            <span className="metric-icon">🎮</span>
          </div>
          <div className="metric-value">
            {sessionStats.loading ? '…' : sessionStats.totalSessions}
          </div>
          <p className="metric-desc">Completed gaming sessions on record</p>
          <Link to="/sessions" className="metric-link">
            View all sessions →
          </Link>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Total Gaming Time</span>
            <span className="metric-icon">⏱</span>
          </div>
          <div className="metric-value">
            {sessionStats.loading
              ? '…'
              : formatDuration(sessionStats.totalDurationSeconds)}
          </div>
          <p className="metric-desc">Tracked across all logged sessions</p>
          <Link to="/sessions" className="metric-link">
            Session history →
          </Link>
        </div>
      </div>

      {/* Feature Navigation Cards */}
      <div className="dashboard-content-grid">
        <div className="panel-card">
          <div className="panel-header">
            <h2 className="panel-title">🧠 Gaming Second Brain</h2>
            <Link to="/memories" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Store tactical takeaways, cross-hair lineups, and clutch moments so you never lose
            valuable gaming knowledge.
          </p>
          <div className="panel-action-box">
            <Link to="/memories" className="btn-secondary w-full text-center">
              Explore Memories Repository
            </Link>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h2 className="panel-title">⚡ Productivity & Tasks</h2>
            <Link to="/tasks" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Transition smoothly from high-intensity gaming sessions into focused study or work sprints.
          </p>
          <div className="panel-action-box">
            <Link to="/tasks" className="btn-secondary w-full text-center">
              Manage Productivity Queue
            </Link>
          </div>
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

export default Dashboard;
