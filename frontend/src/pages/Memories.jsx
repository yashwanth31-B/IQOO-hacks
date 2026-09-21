import React from 'react';

export const Memories = () => {
  const hudUrl = `http://${window.location.hostname || 'localhost'}:8000`;

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">
            <span className="logo-symbol">🧠</span> INTELLIGENCE & MEMORY LAYER
          </div>
          <h1 className="page-title">Gaming Second Brain</h1>
          <p className="page-subtitle">Multi-tier cognitive memory vault: Episodic, Semantic, and Procedural.</p>
        </div>
        <div className="page-actions">
          <a
            href={hudUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
          >
            🚀 Open Cyber HUD (Port 8000) ↗
          </a>
        </div>
      </div>

      {/* Featured Banner for Pulled Cyber HUD */}
      <div className="panel-card" style={{ border: '1px solid rgba(56, 189, 248, 0.4)', background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.08) 0%, var(--bg-card) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="badge-connected">● LIVE ON PORT 8000</span>
              <span className="badge-mvp">FASTAPI + NLP ENGINE</span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Cyber Esports HUD & Memory Vault
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.25rem', maxWidth: '600px' }}>
              The newly pulled intelligence layer features interactive match simulations, 3 cognitive memory tiers (Episodic, Semantic, Procedural), tilt pattern mining, and tactical match briefings.
            </p>
          </div>
          <a
            href={hudUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ padding: '0.8rem 1.4rem' }}
          >
            Launch Cockpit HUD ↗
          </a>
        </div>
      </div>

      {/* 5-Step Journey Overview */}
      <div className="dashboard-content-grid">
        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">🎮 1. Live Match Simulation</h3>
          </div>
          <p className="panel-text">
            Ingest live timeline telemetry from Valorant, BGMI, Apex, or Elden Ring with real-time incident tagging.
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#simulator`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Run Live Simulator →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">🗄️ 2. Three Memory Tiers</h3>
          </div>
          <p className="panel-text">
            Browse match incidents (Episodic), player tendencies (Semantic), and reflex habits (Procedural).
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#vault`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              View Memory Vault →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">🔍 3. Natural Language Search</h3>
          </div>
          <p className="panel-text">
            Ask questions like "Why do I keep losing on Haven C site?" and receive synthesized answers citing match rounds.
          </p>
          <div className="panel-action-box">
            <a href={`${hudUrl}/#search`} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full text-center">
              Query Second Brain →
            </a>
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3 className="panel-title">📊 4. Cross-Session Patterns</h3>
          </div>
          <p className="panel-text">
            Analyze the 11:00 PM fatigue cliff and tilt-versus-outcome telemetry charts to break losing streaks.
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
