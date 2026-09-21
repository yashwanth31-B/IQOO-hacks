import React, { useEffect } from 'react';

export const TaskConfirmModal = ({
  isOpen,
  onClose,
  onConfirm,
  taskTitle = '',
  isDeleting = false
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !isDeleting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDeleting, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '440px' }}
      >
        <div className="modal-header">
          <div>
            <h2 className="modal-title" style={{ color: 'var(--status-danger)' }}>
              🗑️ Delete Task
            </h2>
            <p className="modal-subtitle">This action cannot be undone.</p>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close modal"
            disabled={isDeleting}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: '0.5rem 0', color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
          Are you sure you want to permanently delete{' '}
          <strong style={{ color: 'var(--text-primary)' }}>
            "{taskTitle || 'this task'}"
          </strong>
          ?
        </div>

        <div className="modal-actions" style={{ marginTop: '1.25rem' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? (
              <>
                <span className="btn-spinner" /> Deleting...
              </>
            ) : (
              'Delete Task'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TaskConfirmModal;
