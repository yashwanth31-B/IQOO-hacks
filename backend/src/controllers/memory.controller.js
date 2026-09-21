const memoryService = require('../services/memory.service');
const {
  isValidUUID,
  validateCreateMemoryInput,
  validateUpdateMemoryInput,
  validatePagination
} = require('../utils/validation.utils');

/**
 * Create a new gaming memory
 * POST /api/memories
 */
const createMemory = async (req, res, next) => {
  try {
    const validation = validateCreateMemoryInput(req.body || {});
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const { title, summary, memoryType, sessionId, metadata } = req.body;

    const memory = await memoryService.createMemory({
      userId: req.user.id,
      title,
      summary,
      memoryType,
      sessionId,
      metadata
    });

    return res.status(201).json({
      success: true,
      message: 'Gaming memory created successfully',
      memory
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
 * Retrieve paginated gaming memories with optional filtering
 * GET /api/memories
 */
const getMemories = async (req, res, next) => {
  try {
    const paginationResult = validatePagination(req.query);
    if (!paginationResult.isValid) {
      return res.status(400).json({
        success: false,
        message: paginationResult.error
      });
    }

    const { memoryType, sessionId } = req.query;

    if (sessionId !== undefined && sessionId !== null && !isValidUUID(sessionId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid sessionId parameter: must be a valid UUID'
      });
    }

    const result = await memoryService.getMemories({
      userId: req.user.id,
      page: paginationResult.page,
      limit: paginationResult.limit,
      memoryType,
      sessionId
    });

    return res.status(200).json({
      success: true,
      memories: result.memories,
      pagination: result.pagination
    });
  } catch (error) {
    return next(error);
  }
};

/**
 * Retrieve a single gaming memory by ID
 * GET /api/memories/:id
 */
const getMemoryById = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid memory ID format: must be a valid UUID'
      });
    }

    const memory = await memoryService.getMemoryById({
      memoryId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      memory
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
 * Update gaming memory
 * PATCH /api/memories/:id
 */
const updateMemory = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid memory ID format: must be a valid UUID'
      });
    }

    const validation = validateUpdateMemoryInput(req.body);
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const memory = await memoryService.updateMemory({
      memoryId: id,
      userId: req.user.id,
      updates: req.body
    });

    return res.status(200).json({
      success: true,
      message: 'Gaming memory updated successfully',
      memory
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
 * Delete gaming memory
 * DELETE /api/memories/:id
 */
const deleteMemory = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid memory ID format: must be a valid UUID'
      });
    }

    await memoryService.deleteMemory({
      memoryId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      message: 'Gaming memory deleted successfully'
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
  createMemory,
  getMemories,
  getMemoryById,
  updateMemory,
  deleteMemory
};
