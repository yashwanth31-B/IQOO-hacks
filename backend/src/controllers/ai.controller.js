const aiService = require('../services/ai.service');
const chatHistoryService = require('../services/chat-history.service');
const {
  validateAiChatInput,
  validateCreateConversationInput,
  validatePagination,
  isValidUUID
} = require('../utils/validation.utils');

/**
 * Handle AI Copilot Chat requests
 * POST /api/ai/chat
 */
const chat = async (req, res, next) => {
  try {
    const validation = validateAiChatInput(req.body || {});
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const { message, conversationId } = validation;

    const data = await aiService.processChat({
      userId: req.user.id,
      message,
      conversationId
    });

    return res.status(200).json({
      success: true,
      data
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
 * Create a new conversation explicitly
 * POST /api/ai/conversations
 */
const createConversation = async (req, res, next) => {
  try {
    const validation = validateCreateConversationInput(req.body || {});
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const conversation = await chatHistoryService.createConversation({
      userId: req.user.id,
      title: validation.title
    });

    return res.status(201).json({
      success: true,
      data: {
        conversation
      }
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
 * List conversations belonging to the authenticated user
 * GET /api/ai/conversations
 */
const listConversations = async (req, res, next) => {
  try {
    const paginationValidation = validatePagination(req.query || {});
    if (!paginationValidation.isValid) {
      return res.status(400).json({
        success: false,
        message: paginationValidation.error
      });
    }

    const { page, limit } = paginationValidation;

    const { conversations, pagination } = await chatHistoryService.listUserConversations(
      req.user.id,
      { page, limit }
    );

    return res.status(200).json({
      success: true,
      data: {
        conversations,
        pagination
      }
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
 * Retrieve a specific conversation and its messages
 * GET /api/ai/conversations/:id
 */
const getConversation = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid conversation ID format: must be a valid UUID'
      });
    }

    const conversation = await chatHistoryService.getConversation(id, req.user.id);

    return res.status(200).json({
      success: true,
      data: {
        conversation
      }
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
 * Delete a user's conversation
 * DELETE /api/ai/conversations/:id
 */
const deleteConversation = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid conversation ID format: must be a valid UUID'
      });
    }

    await chatHistoryService.deleteUserConversation(id, req.user.id);

    return res.status(200).json({
      success: true,
      message: 'Conversation deleted successfully',
      data: {
        id
      }
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
 * Check health & status of the deployed Python FastAPI Second Brain service
 * GET /api/ai/second-brain/status
 */
const getSecondBrainStatus = async (req, res, next) => {
  try {
    const status = await aiService.checkSecondBrainHealth();
    return res.status(200).json({
      success: true,
      data: status
    });
  } catch (error) {
    return next(error);
  }
};

module.exports = {
  chat,
  createConversation,
  listConversations,
  getConversation,
  deleteConversation,
  getSecondBrainStatus
};
