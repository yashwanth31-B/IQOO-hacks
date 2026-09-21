import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../services/api';
import { formatDuration } from '../utils/date.utils';
import SessionHistoryList from '../components/SessionHistoryList';
import { SECOND_BRAIN_URL } from '../utils/constants';

/**
 * GAMING SECOND BRAIN — "BEFORE"
 * Accumulated gaming knowledge, past gaming session history, cognitive memories
 * (Episodic, Semantic, Procedural), peak performance records, and cross-session patterns.
 */
export const Memories = () => {
  const navigate = useNavigate();
  const hudUrl = SECOND_BRAIN_URL;

  const [stats, setStats] = useState({
    totalSessions: 0,
    bestScore: null,
    totalDurationSeconds: 0,
    memoriesCount: 0,
    loading: true
  });

  const loadBrainStats = useCallback(async () => {
    try {
      const [sessionsRes, memoriesRes] = await Promise.allSettled([
        api.get('/sessions?page=1&limit=100'),
        api.get('/memories?limit=50')
      ]);

      let totalSessions = 0;
      let bestScore = null;
      let totalDurationSeconds = 0;
      let memoriesCount = 0;

      if (sessionsRes.status === 'fulfilled' && sessionsRes.value?.success) {
        const list = sessionsRes.value.sessions || [];
        totalSessions = sessionsRes.value.pagination?.total ?? list.length;
        list.forEach((s) => {
          totalDurationSeconds += Number(s.duration) || 0;
          if (s.score !== null && s.score !== undefined) {
            const num = Number(s.score);
            if (bestScore === null || num > bestScore) {
              bestScore = num;
            }
          }
        });
      }

      if (memoriesRes.status === 'fulfilled' && memoriesRes.value?.success) {
        const memList = memoriesRes.value.memories || [];
        memoriesCount = memoriesRes.value.pagination?.total ?? memList.length;
      }

      setStats({
        totalSessions,
        bestScore,
        totalDurationSeconds,
        memoriesCount,
        loading: false
      });
    } catch {
      setStats((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    loadBrainStats();
  }, [loadBrainStats]);

  return (
    <div className="page-container">
      {/* 1. Header: GAMING SECOND BRAIN ("BEFORE") */}
      <div className="page-header">
        <div>
          <div className="header-eyebrow">
            <span className="logo-symbol">🧠</span>
            <span className="badge-connected">ACCUMULATED KNOWLEDGE</span>
            <span className="badge-mvp">TIER 2 · "BEFORE"</span>
          </div>
          <h1 className="page-title">Gaming Second Brain</h1>
          <p className="page-subtitle">
            Accumulated gaming knowledge, past match archives, cognitive memory tiers, and cross-session pattern discovery.
          </p>
        </div>
        <div className="page-actions">
          <a
            href={hudUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            title="Launch external Python NLP simulation cockpit"
          >
            🚀 Open Cyber HUD ↗
          </a>
        </div>
      </div>

      {/* 2. Peak Performance & Brain Records ("BEFORE" Intelligence Summary) */}
      <div className="metrics-grid mb-4">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Peak Score Record</span>
            <span className="metric-icon">🏆</span>
          </div>
          <div className="metric-value">
            {stats.loading ? '…' : (stats.bestScore !== null ? stats.bestScore : '--')}
          </div>
          <p className="metric-desc">All-time highest recorded score across sessions</p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Archived Sessions</span>
            <span className="metric-icon">🗄️</span>
          </div>
          <div className="metric-value">
            {stats.loading ? '…' : stats.totalSessions}
          </div>
          <p className="metric-desc">Historical matches preserved in Second Brain</p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Accumulated Playtime</span>
            <span className="metric-icon">⏳</span>
          </div>
          <div className="metric-value">
            {stats.loading ? '…' : formatDuration(stats.totalDurationSeconds)}
          </div>
          <p className="metric-desc">Total gameplay tracked across all archives</p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Cognitive Memories</span>
            <span className="metric-icon">🧩</span>
          </div>
          <div className="metric-value">
            {stats.loading ? '…' : stats.memoriesCount}
          </div>
          <p className="metric-desc">Episodic, Semantic & Procedural knowledge units</p>
        </div>
      </div>

      {/* 3. Historical Gaming Sessions Archive (Moved from Sessions to Second Brain) */}
      <div className="panel-card mb-4">
        <div style={{ marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                🗂️ Past Match Archives & Match Logs
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
                Complete archive of ended gaming sessions, scores, tactical notes, and performance evaluations.
              </p>
            </div>
            <Link to="/sessions" className="btn-secondary" style={{ fontSize: '0.85rem', padding: '0.45rem 0.9rem' }}>
              Switch to Cyber HUD ("NOW") →
            </Link>
          </div>
        </div>

        <SessionHistoryList
          onStartSessionClick={() => navigate('/sessions')}
        />
      </div>

      {/* 4. Multi-Tier Cognitive Memory Vault Overview */}
      <div className="panel-card mb-4" style={{ border: '1px solid rgba(56, 189, 248, 0.4)', background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.08) 0%, var(--bg-card) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="badge-connected">● LIVE NLP ENGINE</span>
              <span className="badge-mvp">3 COGNITIVE TIERS</span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Cognitive Architecture & Tilt Pattern Mining
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.25rem', maxWidth: '650px' }}>
              The Second Brain engine indexes match incidents, player tendencies, and reflex habits. It tracks the <strong>11:00 PM fatigue cliff</strong> and analyzes tilt-versus-outcome correlation across your entire gaming history.
            </p>
          </div>
          <a
            href={hudUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ padding: '0.8rem 1.4rem' }}
          >
            Launch Cockpit Simulator ↗
          </a>
        </div>
      </div>

      {/* 5. Four Intelligence Modules */}
      <div className="dashboard-content-grid">
        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">🎮 1. Episodic Memory</h3>
          </div>
          <p className="panel-text">
            Specific round moments, clutch timelines, and high-intensity match incidents indexed chronologically.
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#vault`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Inspect Episodic Vault →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">🧠 2. Semantic Memory</h3>
          </div>
          <p className="panel-text">
            Player habits, weapon recoil familiarity, map callouts, and enduring tactical tendencies.
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#vault`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Inspect Semantic Vault →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">⚡ 3. Procedural Memory</h3>
          </div>
          <p className="panel-text">
            Actionable execution protocols: "When Haven C is smoked, fall back to garage anchor".
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#vault`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Inspect Procedural Vault →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">📊 4. Cross-Session Patterns</h3>
          </div>
          <p className="panel-text">
            Long-term analytics: detect performance degradation past 75 minutes, late-night tilt patterns, and win-streak warmups.
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#patterns`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Analyze Patterns →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Memories;
