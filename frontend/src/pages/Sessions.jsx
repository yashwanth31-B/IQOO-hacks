import React from 'react';
import EmptyState from '../components/EmptyState';

export const Sessions = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gaming Sessions</h1>
          <p className="page-subtitle">Track, review, and analyze your competitive and casual gaming sessions.</p>
        </div>
        <div className="page-actions">
          <button className="btn-primary" disabled title="Will be implemented in upcoming steps">
            + Start Session
          </button>
        </div>
      </div>

      <div className="panel-card">
        <EmptyState
          icon="🎮"
          title="Session Tracking Hub"
          description="Interactive session timers, game selectors, performance score logging, and duration telemetry will be mounted here in Step 9."
        />
      </div>
    </div>
  );
};

export default Sessions;
