import React, { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../services/api';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';
import TaskItem from '../components/TaskItem';
import TaskModal from '../components/TaskModal';
import TaskConfirmModal from '../components/TaskConfirmModal';

export const Tasks = () => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filtering & Search
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'active' | 'completed' | 'high'
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [taskToEdit, setTaskToEdit] = useState(null);
  const [taskToDelete, setTaskToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // In-flight toggles
  const [togglingIds, setTogglingIds] = useState(new Set());

  // Load real tasks from backend
  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.getTasks({ limit: 100 });
      if (response && response.success && Array.isArray(response.tasks)) {
        setTasks(response.tasks);
      } else if (response && Array.isArray(response.data)) {
        setTasks(response.data);
      } else {
        setTasks([]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load productivity tasks from server.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Statistics
  const stats = useMemo(() => {
    const total = tasks.length;
    const active = tasks.filter((t) => !t.completed).length;
    const completed = tasks.filter((t) => t.completed).length;
    const highPriority = tasks.filter(
      (t) => t.priority?.toLowerCase() === 'high' && !t.completed
    ).length;
    return { total, active, completed, highPriority };
  }, [tasks]);

  // Filtered tasks
  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      // Filter by tab
      if (activeFilter === 'active' && t.completed) return false;
      if (activeFilter === 'completed' && !t.completed) return false;
      if (activeFilter === 'high' && t.priority?.toLowerCase() !== 'high') return false;

      // Filter by search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = t.title?.toLowerCase().includes(q);
        const matchesDesc = t.description?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesDesc) return false;
      }

      return true;
    });
  }, [tasks, activeFilter, searchQuery]);

  // Complete / Incomplete toggle
  const handleToggleComplete = async (taskId, currentStatus) => {
    if (togglingIds.has(taskId)) return;

    // Optimistic UI update
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, completed: !currentStatus } : t))
    );
    setTogglingIds((prev) => new Set(prev).add(taskId));

    try {
      let res;
      if (currentStatus) {
        res = await api.incompleteTask(taskId);
      } else {
        res = await api.completeTask(taskId);
      }

      if (res && res.success && res.task) {
        setTasks((prev) =>
          prev.map((t) => (t.id === taskId ? res.task : t))
        );
      }
    } catch (err) {
      // Revert optimistic update on failure
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, completed: currentStatus } : t))
      );
      setError(err.message || 'Failed to update task completion status.');
    } finally {
      setTogglingIds((prev) => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    }
  };

  // Open Create Modal
  const handleOpenCreateModal = () => {
    setTaskToEdit(null);
    setIsModalOpen(true);
  };

  // Open Edit Modal
  const handleOpenEditModal = (task) => {
    setTaskToEdit(task);
    setIsModalOpen(true);
  };

  // Saved task handler (create or edit)
  const handleTaskSaved = (savedTask, isEdit) => {
    if (isEdit) {
      setTasks((prev) =>
        prev.map((t) => (t.id === savedTask.id ? savedTask : t))
      );
    } else {
      setTasks((prev) => [savedTask, ...prev]);
    }
  };

  // Open Delete Modal
  const handleOpenDeleteModal = (task) => {
    setTaskToDelete(task);
  };

  // Confirm Delete
  const handleConfirmDelete = async () => {
    if (!taskToDelete) return;
    setIsDeleting(true);
    try {
      await api.deleteTask(taskToDelete.id);
      setTasks((prev) => prev.filter((t) => t.id !== taskToDelete.id));
      setTaskToDelete(null);
    } catch (err) {
      setError(err.message || 'Failed to delete task. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="header-eyebrow">
            <span className="logo-symbol">⚡</span> COGNITIVE FOCUS LAYER
          </div>
          <h1 className="page-title">Productivity Tasks</h1>
          <p className="page-subtitle">
            Transition smoothly from gaming duels into focused homework, study sprints, and routine mastery.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleOpenCreateModal}
          >
            + New Task
          </button>
        </div>
      </div>

      {/* Error Message Banner */}
      <ErrorMessage message={error} onRetry={loadTasks} />

      {/* Statistics Bar */}
      <div className="tasks-stats-grid">
        <div
          className={`stat-card ${activeFilter === 'all' ? 'stat-card-active' : ''}`}
          onClick={() => setActiveFilter('all')}
          role="button"
          tabIndex={0}
        >
          <div className="stat-label">Total Tasks</div>
          <div className="stat-value">{stats.total}</div>
        </div>
        <div
          className={`stat-card ${activeFilter === 'active' ? 'stat-card-active' : ''}`}
          onClick={() => setActiveFilter('active')}
          role="button"
          tabIndex={0}
        >
          <div className="stat-label">Active Sprints</div>
          <div className="stat-value" style={{ color: 'var(--accent)' }}>
            {stats.active}
          </div>
        </div>
        <div
          className={`stat-card ${activeFilter === 'high' ? 'stat-card-active' : ''}`}
          onClick={() => setActiveFilter('high')}
          role="button"
          tabIndex={0}
        >
          <div className="stat-label">High Priority</div>
          <div className="stat-value" style={{ color: 'var(--status-danger)' }}>
            {stats.highPriority}
          </div>
        </div>
        <div
          className={`stat-card ${activeFilter === 'completed' ? 'stat-card-active' : ''}`}
          onClick={() => setActiveFilter('completed')}
          role="button"
          tabIndex={0}
        >
          <div className="stat-label">Completed</div>
          <div className="stat-value" style={{ color: 'var(--status-online)' }}>
            {stats.completed}
          </div>
        </div>
      </div>

      {/* Task Queue Container */}
      <div className="panel-card tasks-container-panel">
        {/* Filter Controls & Search */}
        <div className="tasks-toolbar">
          {/* Tabs */}
          <div className="tasks-filter-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeFilter === 'all'}
              className={`filter-tab ${activeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setActiveFilter('all')}
            >
              All <span className="tab-count">{stats.total}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeFilter === 'active'}
              className={`filter-tab ${activeFilter === 'active' ? 'active' : ''}`}
              onClick={() => setActiveFilter('active')}
            >
              Active <span className="tab-count">{stats.active}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeFilter === 'high'}
              className={`filter-tab ${activeFilter === 'high' ? 'active' : ''}`}
              onClick={() => setActiveFilter('high')}
            >
              🔥 High Priority{' '}
              <span className="tab-count">{tasks.filter((t) => t.priority?.toLowerCase() === 'high').length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeFilter === 'completed'}
              className={`filter-tab ${activeFilter === 'completed' ? 'active' : ''}`}
              onClick={() => setActiveFilter('completed')}
            >
              Completed <span className="tab-count">{stats.completed}</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="tasks-search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              className="tasks-search-input"
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search tasks"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Task List / States */}
        {loading ? (
          <div style={{ padding: '3rem 1rem' }}>
            <LoadingSpinner text="Retrieving productivity tasks from Second Brain..." />
          </div>
        ) : tasks.length === 0 ? (
          <EmptyState
            icon="⚡"
            title="Productivity Task Queue is Empty"
            description="Bridge the gap between gaming sessions and real-world focus. Add your study goals, homework assignments, or physical warmup routines."
            action={
              <button
                type="button"
                className="btn-primary"
                onClick={handleOpenCreateModal}
              >
                + Create First Task
              </button>
            }
          />
        ) : filteredTasks.length === 0 ? (
          <EmptyState
            icon="🔍"
            title="No Matching Tasks Found"
            description={`No tasks found for filter "${activeFilter}" ${searchQuery ? `matching "${searchQuery}"` : ''}.`}
            action={
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setActiveFilter('all');
                  setSearchQuery('');
                }}
              >
                Reset Filters
              </button>
            }
          />
        ) : (
          <div className="tasks-list">
            {filteredTasks.map((task) => (
              <TaskItem
                key={task.id}
                task={task}
                onToggleComplete={handleToggleComplete}
                onEdit={handleOpenEditModal}
                onDelete={handleOpenDeleteModal}
                isToggling={togglingIds.has(task.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create / Edit Modal */}
      <TaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onTaskSaved={handleTaskSaved}
        taskToEdit={taskToEdit}
      />

      {/* Delete Confirmation Modal */}
      <TaskConfirmModal
        isOpen={Boolean(taskToDelete)}
        onClose={() => setTaskToDelete(null)}
        onConfirm={handleConfirmDelete}
        taskTitle={taskToDelete?.title || ''}
        isDeleting={isDeleting}
      />
    </div>
  );
};

export default Tasks;
