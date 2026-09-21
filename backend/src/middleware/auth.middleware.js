const { verifyToken } = require('../utils/jwt.utils');

/**
 * Authentication middleware validating JWT bearer token
 */
const requireAuth = (req, res, next) => {
  const authHeader = req.headers.authorization;

  // 1. Check if Authorization header is provided
  if (!authHeader) {
    return res.status(401).json({
      success: false,
      message: 'Authentication token required'
    });
  }

  // 2. Check Bearer format
  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0] !== 'Bearer' || !parts[1].trim()) {
    return res.status(401).json({
      success: false,
      message: 'Invalid token format. Format must be Bearer <token>'
    });
  }

  const token = parts[1].trim();

  // 3. Verify JWT
  try {
    const decoded = verifyToken(token);

    // 4 & 5. Extract user info and attach to request
    req.user = {
      id: decoded.userId,
      email: decoded.email
    };

    // 6. Proceed to next handler
    return next();
  } catch (error) {
    // 7. Handle token errors
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({
        success: false,
        message: 'Authentication token expired'
      });
    }

    return res.status(401).json({
      success: false,
      message: 'Invalid authentication token'
    });
  }
};

module.exports = {
  requireAuth
};
