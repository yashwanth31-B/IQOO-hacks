/**
 * Validation utilities for authentication
 */

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 6;

/**
 * Validate email format
 * @param {string} email 
 * @returns {boolean}
 */
const isValidEmail = (email) => {
  if (typeof email !== 'string') return false;
  return EMAIL_REGEX.test(email.trim());
};

/**
 * Normalize email by trimming and converting to lowercase
 * @param {string} email 
 * @returns {string}
 */
const normalizeEmail = (email) => {
  return typeof email === 'string' ? email.trim().toLowerCase() : '';
};

/**
 * Validate signup payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateSignupInput = ({ name, email, password }) => {
  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return { isValid: false, error: 'Name is required' };
  }

  if (!email || typeof email !== 'string' || email.trim().length === 0) {
    return { isValid: false, error: 'Email is required' };
  }

  if (!isValidEmail(email)) {
    return { isValid: false, error: 'Invalid email format' };
  }

  if (!password || typeof password !== 'string') {
    return { isValid: false, error: 'Password is required' };
  }

  if (password.length < MIN_PASSWORD_LENGTH) {
    return { 
      isValid: false, 
      error: `Password must be at least ${MIN_PASSWORD_LENGTH} characters long` 
    };
  }

  return { isValid: true };
};

/**
 * Validate login payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateLoginInput = ({ email, password }) => {
  if (!email || typeof email !== 'string' || email.trim().length === 0) {
    return { isValid: false, error: 'Email is required' };
  }

  if (!isValidEmail(email)) {
    return { isValid: false, error: 'Invalid email format' };
  }

  if (!password || typeof password !== 'string' || password.length === 0) {
    return { isValid: false, error: 'Password is required' };
  }

  return { isValid: true };
};

module.exports = {
  isValidEmail,
  normalizeEmail,
  validateSignupInput,
  validateLoginInput,
  MIN_PASSWORD_LENGTH
};
