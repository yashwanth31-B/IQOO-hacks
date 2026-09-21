import React, { useState, useEffect } from 'react';
import api from '../services/api';
import ErrorMessage from './ErrorMessage';

const PRIORITY_OPTIONS = [
  { value: 'low', label: '🌱 Low Priority', color: 'var(--accent)' },
  { value: 'medium', label: '⚡ Medium Priority', color: 'var(--status-warning)' },
  { value: 'high', label: '🔥 High Priority', color: 'var(--status-danger)' }
];

const toLocalInputValue = (isoStr) => {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '';
  }
};

export const TaskModal = ({ isOpen, onClose, onTaskSaved, taskToEdit = null }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('medium');
  const [dueDate, setDueDate] = useState('');
  const [estimatedMinutes, setEstimatedMinutes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Populate or reset form when taskToEdit or isOpen changes
  useEffect(() => {
    if (isOpen) {
      if (taskToEdit) {
        setTitle(taskToEdit.title || '');
        setDescription(taskToEdit.description || '');
        setPriority(taskToEdit.priority || 'medium');
        setDueDate(toLocalInputValue(taskToEdit.dueDate));
        setEstimatedMinutes(
          taskToEdit.estimatedMinutes !== null && taskToEdit.estimatedMinutes !== undefined
            ? String(taskToEdit.estimatedMinutes)
            : ''
        );
      } else {
        setTitle('');
        setDescription('');
        setPriority('medium');
        setDueDate('');
        setEstimatedMinutes('');
      }
      setError('');
    }
  }, [isOpen, taskToEdit]);

  // Handle Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, submitting, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError('Title is required');
      return;
    }

    if (trimmedTitle.length > 255) {
      setError('Title must not exceed 255 characters');
      return;
    }

    let parsedMinutes = null;
    if (estimatedMinutes !== '') {
      parsedMinutes = parseInt(estimatedMinutes, 10);
      if (isNaN(parsedMinutes) || parsedMinutes <= 0) {
        setError('Estimated minutes must be a positive number greater than 0');
        return;
      }
    }

    let parsedDueDate = null;
    if (dueDate) {
      const d = new Date(dueDate);
      if (isNaN(d.getTime())) {
        setError('Please provide a valid due date');
        return;
      }
      parsedDueDate = d.toISOString();
    }

    setSubmitting(true);
    try {
      const payload = {
        title: trimmedTitle,
        description: description.trim() || null,
        priority: priority.toLowerCase(),
        dueDate: parsedDueDate,
        estimatedMinutes: parsedMinutes
      };

      let response;
      if (taskToEdit) {
        response = await api.updateTask(taskToEdit.id, payload);
      } else {
        response = await api.createTask(payload);
      }

      if (response && response.success && response.task) {
        if (onTaskSaved) {
          onTaskSaved(response.task, Boolean(taskToEdit));
        }
        onClose();
      } else {
        throw new Error(response.message || 'Failed to save task');
      }
    } catch (err) {
      setError(err.message || 'Failed to save task. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '540px' }}
      >
        <div className="modal-header">
          <div>
            <h2 className="modal-title">
              {taskToEdit ? '✏️ Edit Task' : '⚡ New Productivity Task'}
            </h2>
            <p className="modal-subtitle">
              {taskToEdit
                ? 'Update task priorities, deadlines, and study sprints.'
                : 'Queue up homework, coding, or focused study after gaming.'}
            </p>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close modal"
            disabled={submitting}
          >
            ✕
          </button>
        </div>

        <ErrorMessage message={error} />

        <form className="modal-form" onSubmit={handleSubmit}>
          {/* Title */}
          <div className="form-group">
            <label htmlFor="task-title">
              Task Title <span style={{ color: 'var(--status-danger)' }}>*</span>
            </label>
            <input
              id="task-title"
              type="text"
              required
              autoFocus
              maxLength={255}
              placeholder="e.g. Finish Math Problem Set 4, Review Valorant VOD"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Description */}
          <div className="form-group mt-2">
            <label htmlFor="task-desc">Description / Notes (Optional)</label>
            <textarea
              id="task-desc"
              rows="3"
              placeholder="e.g. Chapter 6 exercises 1-15. Focus on quadratic formula and graphing."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Priority & Estimated Minutes Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }} className="mt-2">
            <div className="form-group">
              <label htmlFor="task-priority">Priority</label>
              <select
                id="task-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                disabled={submitting}
              >
                {PRIORITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="task-estimated-mins">Est. Minutes</label>
              <input
                id="task-estimated-mins"
                type="number"
                min="1"
                max="1440"
                placeholder="e.g. 45"
                value={estimatedMinutes}
                onChange={(e) => setEstimatedMinutes(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          {/* Due Date */}
          <div className="form-group mt-2">
            <label htmlFor="task-due-date">Due Date & Time (Optional)</label>
            <input
              id="task-due-date"
              type="datetime-local"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Modal Actions */}
          <div className="modal-actions" style={{ marginTop: '1.25rem' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting || !title.trim()}
            >
              {submitting ? (
                <>
                  <span className="btn-spinner" /> Saving...
                </>
              ) : taskToEdit ? (
                'Save Changes'
              ) : (
                '+ Create Task'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TaskModal;
