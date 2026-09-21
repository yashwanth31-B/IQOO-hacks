import React from 'react';

export const ErrorMessage = ({ message, onRetry }) => {
  if (!message) return null;

  return (
    <div className="error-banner" role="alert">
      <span className="error-icon">⚠️</span>
      <span className="error-text">{message}</span>
      {onRetry && (
        <button className="btn-retry" onClick={onRetry} type="button">
          Retry
        </button>
      )}
    </div>
  );
};

export default ErrorMessage;
