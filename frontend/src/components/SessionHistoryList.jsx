import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { formatDuration, formatSessionDate } from '../utils/date.utils';
import LoadingSpinner from './LoadingSpinner';
import ErrorMessage from './ErrorMessage';
import EmptyState from './EmptyState';

export const SessionHistoryList = ({ refreshTrigger, onStartSessionClick }) => {
  const [sessions, setSessions] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, limit: 10, total: 0, totalPages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  const fetchSessions = useCallback(async (page = 1) => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get(`/sessions?page=${page}&limit=10`);
      if (response && response.success) {
        setSessions(response.sessions || []);
        if (response.pagination) {
          setPagination(response.pagination);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load session history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions(pagination.page);
  }, [fetchSessions, refreshTrigger, pagination.page]);

  const handleDeleteSession = async (sessionId) => {
    if (!window.confirm('Are you sure you want to delete this session record?')) {
      return;
    }

    setDeletingId(sessionId);
    try {
      await api.delete(`/sessions/${sessionId}`);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setPagination((prev) => ({ ...prev, total: Math.max(0, prev.total - 1) }));
    } catch (err) {
      alert(err.message || 'Failed to delete session');
    } finally {
      setDeletingId(null);
    }
  };

  if (loading && sessions.length === 0) {
    return <LoadingSpinner message="Loading session history..." />;
  }

  return (
    <div className="session-history-container">
      <div className="history-header-row">
        <div>
          <h2 className="section-title">Session History</h2>
          <p className="section-subtitle">
            {pagination.total} {pagination.total === 1 ? 'session' : 'sessions'} recorded
          </p>
        </div>
        <button
          className="btn-refresh"
          onClick={() => fetchSessions(pagination.page)}
          disabled={loading}
          title="Refresh session list"
        >
          {loading ? '⟳ Refreshing...' : '⟳ Refresh'}
        </button>
      </div>

      <ErrorMessage message={error} onRetry={() => fetchSessions(pagination.page)} />

      {sessions.length === 0 && !loading ? (
        <EmptyState
          icon="🎮"
          title="NO GAMING HISTORY"
          description="Your completed gaming sessions will appear here. Start your first session to track performance and build your Second Brain."
          action={
            onStartSessionClick && (
              <button className="btn-primary mt-2" onClick={onStartSessionClick}>
                + Start First Session
              </button>
            )
          }
        />
      ) : (
        <div className="sessions-list">
          {sessions.map((session) => (
            <div key={session.id} className="session-card">
              <div className="session-card-header">
                <div className="session-game-badge">
                  <span className="game-icon">🎯</span>
                  <div>
                    <h3 className="game-name">{session.gameName || 'Custom Game'}</h3>
                    <span className="game-platform">{session.platform || 'PC'}</span>
                  </div>
                </div>

                <div className="session-timing">
                  <span className="session-duration-tag">
                    ⏱ {formatDuration(session.duration)}
                  </span>
                  <button
                    className="btn-delete-session"
                    onClick={() => handleDeleteSession(session.id)}
                    disabled={deletingId === session.id}
                    title="Delete session record"
                  >
                    {deletingId === session.id ? '…' : '🗑'}
                  </button>
                </div>
              </div>

              <div className="session-card-body">
                <div className="session-details-grid">
                  <div className="detail-item">
                    <span className="detail-label">Started</span>
                    <span className="detail-value">{formatSessionDate(session.startedAt)}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Ended</span>
                    <span className="detail-value">
                      {session.endedAt ? formatSessionDate(session.endedAt) : 'In Progress'}
                    </span>
                  </div>

                  {session.score !== null && session.score !== undefined && (
                    <div className="detail-item">
                      <span className="detail-label">Final Score</span>
                      <span className="detail-value font-bold text-accent">{session.score}</span>
                    </div>
                  )}

                  {session.performance && (
                    <div className="detail-item">
                      <span className="detail-label">Performance</span>
                      <span className="detail-value performance-tag">
                        {session.performance}
                      </span>
                    </div>
                  )}
                </div>

                {session.notes && (
                  <div className="session-notes-box">
                    <span className="notes-heading">Notes & Tactics:</span>
                    <p className="notes-content">{session.notes}</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {pagination.totalPages > 1 && (
        <div className="pagination-bar">
          <button
            className="btn-pagination"
            disabled={pagination.page <= 1 || loading}
            onClick={() => setPagination((prev) => ({ ...prev, page: prev.page - 1 }))}
          >
            ← Previous
          </button>
          <span className="pagination-info">
            Page {pagination.page} of {pagination.totalPages}
          </span>
          <button
            className="btn-pagination"
            disabled={pagination.page >= pagination.totalPages || loading}
            onClick={() => setPagination((prev) => ({ ...prev, page: prev.page + 1 }))}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
};

export default SessionHistoryList;
