import React from 'react';
import EmptyState from '../components/EmptyState';

export const Tasks = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Productivity Tasks</h1>
          <p className="page-subtitle">Seamlessly transition from gaming into focused study, homework, and work sprints.</p>
        </div>
        <div className="page-actions">
          <button className="btn-primary" disabled title="Will be implemented in upcoming steps">
            + New Task
          </button>
        </div>
      </div>

      <div className="panel-card">
        <EmptyState
          icon="⚡"
          title="Productivity Task Queue"
          description="Interactive task checklists, priority filters, due date alerts, and Focus Mode timers will be mounted here in the next step."
        />
      </div>
    </div>
  );
};

export default Tasks;
