import React, { useState, useEffect } from 'react';
import api from '../services/api';

export const HealthBadge = () => {
  const [status, setStatus] = useState({
    loading: true,
    connected: false,
    database: 'checking',
    message: ''
  });

  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        const data = await api.get('/health');
        if (isMounted) {
          setStatus({
            loading: false,
            connected: data?.success === true,
            database: data?.database || 'unknown',
            message: data?.message || 'API Online'
          });
        }
      } catch (err) {
        if (isMounted) {
          setStatus({
            loading: false,
            connected: false,
            database: 'disconnected',
            message: err.message || 'Offline'
          });
        }
      }
    };

    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  if (status.loading) {
    return (
      <span className="health-badge status-checking">
        <span className="badge-dot"></span> Checking backend...
      </span>
    );
  }

  if (status.connected) {
    return (
      <span className="health-badge status-online" title={`Backend: ${status.message}, Database: ${status.database}`}>
        <span className="badge-dot"></span> System Online
      </span>
    );
  }

  return (
    <span className="health-badge status-offline" title={status.message}>
      <span className="badge-dot"></span> Backend Offline
    </span>
  );
};

export default HealthBadge;
