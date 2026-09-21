const jwt = require('jsonwebtoken');

/**
 * Generate a signed JWT
 * @param {Object} payload 
 * @param {string} [expiresIn] 
 * @returns {string}
 */
const generateToken = (payload, expiresIn) => {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error('JWT_SECRET is not configured in environment variables');
  }

  const expiration = expiresIn || process.env.JWT_EXPIRES_IN || '7d';
  return jwt.sign(payload, secret, { expiresIn: expiration });
};

/**
 * Verify a JWT
 * @param {string} token 
 * @returns {Object} decoded payload
 */
const verifyToken = (token) => {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error('JWT_SECRET is not configured in environment variables');
  }

  return jwt.verify(token, secret);
};

module.exports = {
  generateToken,
  verifyToken
};
