const bcrypt = require('bcryptjs');
const db = require('../db');
const { generateToken } = require('../utils/jwt.utils');
const { normalizeEmail } = require('../utils/validation.utils');

const SALT_ROUNDS = 10;

/**
 * Register a new user
 * @param {Object} userData 
 * @param {string} userData.name
 * @param {string} userData.email
 * @param {string} userData.password
 * @returns {Promise<Object>} safe user record
 */
const signup = async ({ name, email, password }) => {
  const normalizedEmail = normalizeEmail(email);

  // Check if user already exists
  const existingUserCheck = await db.query(
    'SELECT id FROM users WHERE email = $1;',
    [normalizedEmail]
  );

  if (existingUserCheck.rows.length > 0) {
    const error = new Error('An account with this email already exists');
    error.statusCode = 409;
    throw error;
  }

  // Hash password
  const salt = await bcrypt.genSalt(SALT_ROUNDS);
  const passwordHash = await bcrypt.hash(password, salt);

  // Store user in PostgreSQL with parameterized query
  const insertResult = await db.query(
    `INSERT INTO users (name, email, password_hash)
     VALUES ($1, $2, $3)
     RETURNING id, name, email, created_at, updated_at;`,
    [name.trim(), normalizedEmail, passwordHash]
  );

  const newUser = insertResult.rows[0];
  return {
    id: newUser.id,
    name: newUser.name,
    email: newUser.email,
    created_at: newUser.created_at,
    updated_at: newUser.updated_at
  };
};

/**
 * Authenticate user and issue JWT
 * @param {Object} credentials
 * @param {string} credentials.email
 * @param {string} credentials.password
 * @returns {Promise<{ token: string, user: Object }>}
 */
const login = async ({ email, password }) => {
  const normalizedEmail = normalizeEmail(email);

  // Query user by email
  const userResult = await db.query(
    'SELECT id, name, email, password_hash FROM users WHERE email = $1;',
    [normalizedEmail]
  );

  if (userResult.rows.length === 0) {
    // Avoid revealing whether email exists
    const error = new Error('Invalid email or password');
    error.statusCode = 401;
    throw error;
  }

  const user = userResult.rows[0];

  // Compare password against stored hash
  const isMatch = await bcrypt.compare(password, user.password_hash);
  if (!isMatch) {
    const error = new Error('Invalid email or password');
    error.statusCode = 401;
    throw error;
  }

  // Generate JWT token
  const token = generateToken({
    userId: user.id,
    email: user.email
  });

  return {
    token,
    user: {
      id: user.id,
      name: user.name,
      email: user.email
    }
  };
};

/**
 * Retrieve user by ID without password hash
 * @param {string} userId 
 * @returns {Promise<Object|null>}
 */
const getUserById = async (userId) => {
  const result = await db.query(
    'SELECT id, name, email, created_at, updated_at FROM users WHERE id = $1;',
    [userId]
  );

  if (result.rows.length === 0) {
    return null;
  }

  return result.rows[0];
};

module.exports = {
  signup,
  login,
  getUserById
};
