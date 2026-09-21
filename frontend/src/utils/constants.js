/**
 * Centralized Application Constants
 */

export const AUTH_TOKEN_KEY = 'ai_gaming_copilot_token';

// In combined deployment or behind Vite dev proxy, relative '/api' calls the local host directly.
// When custom VITE_API_BASE_URL is provided (e.g. standalone Vercel deployment), respect it.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
