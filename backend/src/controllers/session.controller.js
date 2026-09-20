const sessionService = require('../services/session.service');
const {
  isValidUUID,
  validateCreateSessionInput,
  validateUpdateSessionInput,
  validatePagination
} = require('../utils/validation.utils');

/**
 * Start a new gaming session
 * POST /api/sessions
 */
const createSession = async (req, res, next) => {
  try {
    const { gameId, score, performance, notes } = req.body || {};

    const validation = validateCreateSessionInput({ gameId, score, performance, notes });
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const session = await sessionService.createSession({
      userId: req.user.id,
      gameId,
      score,
      performance,
      notes
    });

    return res.status(201).json({
      success: true,
      message: 'Gaming session started successfully',
      session
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Retrieve user's currently active gaming session
 * GET /api/sessions/active
 */
const getActiveSession = async (req, res, next) => {
  try {
    const session = await sessionService.getActiveSession(req.user.id);

    return res.status(200).json({
      success: true,
      session
    });
  } catch (error) {
    return next(error);
  }
};

/**
 * Retrieve a specific gaming session
 * GET /api/sessions/:id
 */
const getSessionById = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid session ID format: must be a valid UUID'
      });
    }

    const session = await sessionService.getSessionById({
      sessionId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      session
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Retrieve user's paginated gaming sessions
 * GET /api/sessions
 */
const getUserSessions = async (req, res, next) => {
  try {
    const paginationResult = validatePagination(req.query);
    if (!paginationResult.isValid) {
      return res.status(400).json({
        success: false,
        message: paginationResult.error
      });
    }

    const result = await sessionService.getUserSessions({
      userId: req.user.id,
      page: paginationResult.page,
      limit: paginationResult.limit
    });

    return res.status(200).json({
      success: true,
      sessions: result.sessions,
      pagination: result.pagination
    });
  } catch (error) {
    return next(error);
  }
};

/**
 * Update gaming session details
 * PATCH /api/sessions/:id
 */
const updateSession = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid session ID format: must be a valid UUID'
      });
    }

    const validation = validateUpdateSessionInput(req.body);
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const session = await sessionService.updateSession({
      sessionId: id,
      userId: req.user.id,
      updates: req.body
    });

    return res.status(200).json({
      success: true,
      message: 'Gaming session updated successfully',
      session
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * End an active gaming session
 * POST /api/sessions/:id/end
 */
const endSession = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid session ID format: must be a valid UUID'
      });
    }

    const session = await sessionService.endSession({
      sessionId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      message: 'Gaming session ended successfully',
      session
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Delete a gaming session
 * DELETE /api/sessions/:id
 */
const deleteSession = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid session ID format: must be a valid UUID'
      });
    }

    await sessionService.deleteSession({
      sessionId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      message: 'Gaming session deleted successfully'
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

module.exports = {
  createSession,
  getActiveSession,
  getSessionById,
  getUserSessions,
  updateSession,
  endSession,
  deleteSession
};
