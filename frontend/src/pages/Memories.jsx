import React from 'react';
import EmptyState from '../components/EmptyState';

export const Memories = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gaming Second Brain</h1>
          <p className="page-subtitle">Persistent repository of tactics, highlights, learnings, and gameplay reflections.</p>
        </div>
        <div className="page-actions">
          <button className="btn-primary" disabled title="Will be implemented in upcoming steps">
            + Log Memory
          </button>
        </div>
      </div>

      <div className="panel-card">
        <EmptyState
          icon="🧠"
          title="Second Brain Knowledge Base"
          description="Tactical memory browsing, session-attached highlights, search filters, and AI semantic vector indexing will be integrated here."
        />
      </div>
    </div>
  );
};

export default Memories;
