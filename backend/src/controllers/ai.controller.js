const aiService = require('../services/ai.service');
const { validateAiChatInput } = require('../utils/validation.utils');

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

    const { message } = validation;

    const data = await aiService.processChat({
      userId: req.user.id,
      message
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

module.exports = {
  chat
};
