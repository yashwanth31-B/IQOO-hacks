import React from 'react';
import {
  formatTaskDueDate,
  isTaskOverdue,
  formatEstimatedMinutes
} from '../utils/date.utils';

export const TaskItem = ({
  task,
  onToggleComplete,
  onEdit,
  onDelete,
  isToggling = false
}) => {
  const isOverdue = isTaskOverdue(task.dueDate, task.completed);
  const formattedDueDate = formatTaskDueDate(task.dueDate);
  const formattedMins = formatEstimatedMinutes(task.estimatedMinutes);

  const priorityMeta = {
    high: {
      label: 'High',
      badgeClass: 'badge-priority-high',
      icon: '🔥'
    },
    medium: {
      label: 'Medium',
      badgeClass: 'badge-priority-medium',
      icon: '⚡'
    },
    low: {
      label: 'Low',
      badgeClass: 'badge-priority-low',
      icon: '🌱'
    }
  }[task.priority?.toLowerCase()] || {
    label: 'Medium',
    badgeClass: 'badge-priority-medium',
    icon: '⚡'
  };

  return (
    <div
      className={`task-card ${task.completed ? 'task-card-completed' : ''} priority-${task.priority?.toLowerCase() || 'medium'}`}
      data-task-id={task.id}
    >
      {/* Checkbox */}
      <button
        type="button"
        role="checkbox"
        aria-checked={task.completed}
        aria-label={`Mark "${task.title}" as ${task.completed ? 'incomplete' : 'complete'}`}
        className={`task-checkbox ${task.completed ? 'task-checkbox-checked' : ''}`}
        onClick={() => onToggleComplete(task.id, task.completed)}
        disabled={isToggling}
      >
        {task.completed && <span className="task-checkmark">✓</span>}
      </button>

      {/* Main Body */}
      <div className="task-content">
        <div className="task-title-row">
          <h3 className={`task-title ${task.completed ? 'task-title-completed' : ''}`}>
            {task.title}
          </h3>
        </div>

        {task.description && (
          <p className={`task-desc ${task.completed ? 'task-desc-completed' : ''}`}>
            {task.description}
          </p>
        )}

        {/* Badges / Metadata */}
        <div className="task-meta-row">
          {/* Priority Badge */}
          <span className={`task-badge ${priorityMeta.badgeClass}`}>
            <span className="task-badge-icon">{priorityMeta.icon}</span>
            {priorityMeta.label}
          </span>

          {/* Overdue / Due Date Badge */}
          {formattedDueDate && (
            <span
              className={`task-badge ${
                isOverdue ? 'badge-overdue' : 'badge-due'
              }`}
              title={isOverdue ? 'This task deadline has passed' : 'Target completion deadline'}
            >
              <span className="task-badge-icon">{isOverdue ? '⚠️' : '📅'}</span>
              {isOverdue ? `Overdue (${formattedDueDate})` : formattedDueDate}
            </span>
          )}

          {/* Estimated Minutes */}
          {formattedMins && (
            <span className="task-badge badge-estimated" title="Estimated sprint duration">
              <span className="task-badge-icon">⏱️</span>
              {formattedMins}
            </span>
          )}

          {/* Completed Timestamp Indicator */}
          {task.completed && (
            <span className="task-badge badge-completed-status">
              ✓ Done
            </span>
          )}
        </div>
      </div>

      {/* Action Controls */}
      <div className="task-actions">
        <button
          type="button"
          className="btn-task-action btn-task-edit"
          onClick={() => onEdit(task)}
          title="Edit task"
          aria-label={`Edit task "${task.title}"`}
        >
          ✏️ <span className="task-btn-text">Edit</span>
        </button>
        <button
          type="button"
          className="btn-task-action btn-task-delete"
          onClick={() => onDelete(task)}
          title="Delete task"
          aria-label={`Delete task "${task.title}"`}
        >
          🗑️ <span className="task-btn-text">Delete</span>
        </button>
      </div>
    </div>
  );
};

export default TaskItem;
