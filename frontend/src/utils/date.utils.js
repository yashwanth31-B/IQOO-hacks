/**
 * Date and Duration formatting utilities for Gaming Sessions
 */

/**
 * Format elapsed seconds into HH:MM:SS format
 * @param {number} totalSeconds 
 * @returns {string} e.g. "01:24:37" or "00:05:12"
 */
export const formatElapsedTimer = (totalSeconds) => {
  if (isNaN(totalSeconds) || totalSeconds < 0) return '00:00:00';
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  const pad = (num) => String(num).padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
};

/**
 * Format duration seconds into human-readable format
 * @param {number|null} durationSeconds 
 * @returns {string} e.g. "1h 42m", "58m", "< 1m", or "—"
 */
export const formatDuration = (durationSeconds) => {
  if (durationSeconds === null || durationSeconds === undefined || isNaN(durationSeconds)) {
    return '—';
  }

  const secs = Math.max(0, Math.floor(durationSeconds));
  if (secs < 60) {
    return `${secs}s`;
  }

  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);

  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  return `${minutes}m`;
};

/**
 * Calculate elapsed seconds from a startedAt ISO timestamp
 * @param {string|Date} startedAt 
 * @returns {number}
 */
export const calculateElapsedSeconds = (startedAt) => {
  if (!startedAt) return 0;
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const elapsed = Math.floor((now - start) / 1000);
  return Math.max(0, elapsed);
};

/**
 * Format ISO date string into human-friendly representation
 * @param {string|Date} dateVal 
 * @returns {string} e.g. "Today · 10:32 AM" or "Sep 21, 2026 · 10:32 AM"
 */
export const formatSessionDate = (dateVal) => {
  if (!dateVal) return '—';
  const date = new Date(dateVal);
  if (isNaN(date.getTime())) return '—';

  const now = new Date();
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (isToday) {
    return `Today · ${timeStr}`;
  }

  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear();

  if (isYesterday) {
    return `Yesterday · ${timeStr}`;
  }

  const dateStr = date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  });

  return `${dateStr} · ${timeStr}`;
};

/**
 * Check if a task is overdue
 * @param {string|Date|null} dueDate 
 * @param {boolean} completed 
 * @returns {boolean}
 */
export const isTaskOverdue = (dueDate, completed = false) => {
  if (!dueDate || completed) return false;
  const due = new Date(dueDate).getTime();
  if (isNaN(due)) return false;
  return due < Date.now();
};

/**
 * Format task due date into human readable text
 * @param {string|Date|null} dueDate 
 * @returns {string|null}
 */
export const formatTaskDueDate = (dueDate) => {
  if (!dueDate) return null;
  const date = new Date(dueDate);
  if (isNaN(date.getTime())) return null;

  const now = new Date();
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const isTomorrow =
    date.getDate() === tomorrow.getDate() &&
    date.getMonth() === tomorrow.getMonth() &&
    date.getFullYear() === tomorrow.getFullYear();

  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear();

  const hours = date.getHours();
  const minutes = date.getMinutes();
  const hasSpecificTime = !(hours === 0 && minutes === 0);
  const timeStr = hasSpecificTime
    ? ` · ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : '';

  if (isToday) return `Today${timeStr}`;
  if (isTomorrow) return `Tomorrow${timeStr}`;
  if (isYesterday) return `Yesterday${timeStr}`;

  return date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  }) + timeStr;
};

/**
 * Format estimated minutes to human-readable duration
 * @param {number|null} mins 
 * @returns {string|null}
 */
export const formatEstimatedMinutes = (mins) => {
  if (mins === null || mins === undefined || isNaN(mins) || mins <= 0) return null;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  if (hours > 0 && remainingMins > 0) return `${hours}h ${remainingMins}m`;
  if (hours > 0) return `${hours}h`;
  return `${remainingMins}m`;
};

