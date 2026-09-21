import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import HealthBadge from '../components/HealthBadge';

export const Dashboard = () => {
  const { user } = useAuth();

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gaming Overview</h1>
          <p className="page-subtitle">Welcome back, {user?.name || 'Player'}. Your gaming copilot status.</p>
        </div>
        <div className="page-actions">
          <HealthBadge />
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Active Session</span>
            <span className="metric-icon">🎮</span>
          </div>
          <div className="metric-value">Idle</div>
          <p className="metric-desc">No gaming session currently in progress</p>
          <Link to="/sessions" className="metric-link">
            Launch session tracker →
          </Link>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Second Brain</span>
            <span className="metric-icon">🧠</span>
          </div>
          <div className="metric-value">Active</div>
          <p className="metric-desc">Tactical notes & highlights indexed</p>
          <Link to="/memories" className="metric-link">
            View memories repository →
          </Link>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Productivity Tasks</span>
            <span className="metric-icon">⚡</span>
          </div>
          <div className="metric-value">Ready</div>
          <p className="metric-desc">Tasks queued for post-game transition</p>
          <Link to="/tasks" className="metric-link">
            Open task manager →
          </Link>
        </div>
      </div>

      <div className="dashboard-content-grid">
        <div className="panel-card">
          <div className="panel-header">
            <h2 className="panel-title">AI Copilot Status</h2>
            <span className="badge-roadmap">COMING IN STEP 9+</span>
          </div>
          <div className="placeholder-container">
            <div className="placeholder-icon">🤖</div>
            <h3>Copilot Intelligence Engine</h3>
            <p>
              Natural language memory retrieval, real-time gaming session insights, and
              post-game cooldown recommendations will be connected in subsequent steps.
            </p>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h2 className="panel-title">API Integration Architecture</h2>
            <span className="badge-connected">CONNECTED</span>
          </div>
          <div className="architecture-list">
            <div className="arch-item">
              <span className="arch-status status-ok">✓</span>
              <div>
                <strong>Express & PostgreSQL Backend</strong>
                <p>JWT Auth, Games, Sessions, Memories, Tasks REST APIs</p>
              </div>
            </div>
            <div className="arch-item">
              <span className="arch-status status-ok">✓</span>
              <div>
                <strong>React + Vite Client</strong>
                <p>Authenticated routing, centralized API client, design tokens</p>
              </div>
            </div>
            <div className="arch-item">
              <span className="arch-status status-pending">⏳</span>
              <div>
                <strong>AI & Second Brain Retrieval</strong>
                <p>Natural-language query and session analysis (Team member)</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
