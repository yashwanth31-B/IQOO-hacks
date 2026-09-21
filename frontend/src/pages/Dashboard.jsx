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
          <Link to="/memories" className="metric-link">
            Second Brain archives →
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
          <Link to="/memories" className="metric-link">
            Historical playtime →
          </Link>
        </div>
      </div>

      {/* 4-Tier Architecture Navigation Grid */}
      <div className="dashboard-content-grid">
        <div className="panel-card">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>NOW</span>
              <h2 className="panel-title">🎮 Cyber HUD</h2>
            </div>
            <Link to="/sessions" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Live gaming cockpit: real-time telemetry, active match clock, live performance rating, and match controls.
          </p>
          <div className="panel-action-box">
            <Link to="/sessions" className="btn-secondary w-full text-center">
              Launch Cyber HUD ("NOW")
            </Link>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc' }}>BEFORE</span>
              <h2 className="panel-title">🧠 Gaming Second Brain</h2>
            </div>
            <Link to="/memories" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Accumulated knowledge: past match archives, peak performance records, 3 cognitive tiers, and tilt pattern analysis.
          </p>
          <div className="panel-action-box">
            <Link to="/memories" className="btn-secondary w-full text-center">
              Explore Second Brain ("BEFORE")
            </Link>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>NOW+BEFORE</span>
              <h2 className="panel-title">🤖 AI Copilot</h2>
            </div>
            <Link to="/copilot" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Contextual AI bridge: connects live HUD telemetry with historical Second Brain data for instant tactical answers.
          </p>
          <div className="panel-action-box">
            <Link to="/copilot" className="btn-secondary w-full text-center">
              Ask AI Copilot ("NOW + BEFORE")
            </Link>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(52, 211, 153, 0.15)', color: '#34d399' }}>NEXT</span>
              <h2 className="panel-title">⚡ Productivity</h2>
            </div>
            <Link to="/tasks" className="panel-header-link">Open →</Link>
          </div>
          <p className="panel-text">
            Post-game cooldown: priority tasks, focus mode sprints, and smooth transition from gaming into work/study.
          </p>
          <div className="panel-action-box">
            <Link to="/tasks" className="btn-secondary w-full text-center">
              Manage Productivity ("NEXT")
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
