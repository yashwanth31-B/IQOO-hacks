const authService = require('../services/auth.service');
const { validateSignupInput, validateLoginInput } = require('../utils/validation.utils');

/**
 * Handle user registration
 * POST /api/auth/signup
 */
const signup = async (req, res, next) => {
  try {
    const { name, email, password } = req.body || {};

    // Validate payload
    const validation = validateSignupInput({ name, email, password });
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    // Register user
    const user = await authService.signup({ name, email, password });

    return res.status(201).json({
      success: true,
      message: 'User registered successfully',
      user: {
        id: user.id,
        name: user.name,
        email: user.email
      }
    });
  } catch (error) {
    if (error.statusCode === 409) {
      return res.status(409).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Handle user login
 * POST /api/auth/login
 */
const login = async (req, res, next) => {
  try {
    const { email, password } = req.body || {};

    // Validate payload
    const validation = validateLoginInput({ email, password });
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    // Authenticate user
    const { token, user } = await authService.login({ email, password });

    return res.status(200).json({
      success: true,
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        name: user.name,
        email: user.email
      }
    });
  } catch (error) {
    if (error.statusCode === 401) {
      return res.status(401).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Handle authenticated user profile retrieval
 * GET /api/auth/me
 */
const getMe = async (req, res, next) => {
  try {
    const userId = req.user.id;
    const user = await authService.getUserById(userId);

    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found'
      });
    }

    return res.status(200).json({
      success: true,
      user: {
        id: user.id,
        name: user.name,
        email: user.email
      }
    });
  } catch (error) {
    return next(error);
  }
};

module.exports = {
  signup,
  login,
  getMe
};
