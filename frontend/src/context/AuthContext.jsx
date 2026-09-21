import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { AUTH_TOKEN_KEY } from '../utils/constants';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY) || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Verify stored token on application startup
   */
  const verifyAuth = useCallback(async () => {
    const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!storedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }

    try {
      const response = await api.get('/auth/me');
      if (response && response.success && response.user) {
        setUser(response.user);
        setToken(storedToken);
      } else {
        throw new Error('Invalid user payload');
      }
    } catch {
      // Token is invalid or expired: clear local storage
      localStorage.removeItem(AUTH_TOKEN_KEY);
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    verifyAuth();
  }, [verifyAuth]);

  /**
   * Register a new user account
   * @param {string} name 
   * @param {string} email 
   * @param {string} password 
   */
  const signup = async (name, email, password) => {
    setError(null);
    try {
      const response = await api.post('/auth/signup', { name, email, password });
      if (response && response.success && response.user) {
        // Auto-login to obtain session JWT
        return await login(email, password);
      }
      throw new Error(response.message || 'Registration failed');
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  /**
   * Authenticate existing user
   * @param {string} email 
   * @param {string} password 
   */
  const login = async (email, password) => {
    setError(null);
    try {
      const response = await api.post('/auth/login', { email, password });
      if (response && response.success && response.token && response.user) {
        localStorage.setItem(AUTH_TOKEN_KEY, response.token);
        setToken(response.token);
        setUser(response.user);
        return { success: true, user: response.user };
      }
      throw new Error(response.message || 'Login failed');
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  /**
   * Log out current user
   */
  const logout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setUser(null);
    setToken(null);
    setError(null);
  };

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(user && token),
    error,
    login,
    signup,
    logout,
    verifyAuth
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
