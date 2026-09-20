const gameService = require('../services/game.service');
const { validateGameInput } = require('../utils/validation.utils');

/**
 * Handle game creation
 * POST /api/games
 */
const createGame = async (req, res, next) => {
  try {
    const { name, platform } = req.body || {};

    const validation = validateGameInput({ name, platform });
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const game = await gameService.createGame({ name, platform });

    return res.status(201).json({
      success: true,
      message: 'Game created successfully',
      game
    });
  } catch (error) {
    return next(error);
  }
};

/**
 * Retrieve list of games
 * GET /api/games
 */
const getGames = async (req, res, next) => {
  try {
    const games = await gameService.getAllGames();

    return res.status(200).json({
      success: true,
      games
    });
  } catch (error) {
    return next(error);
  }
};

module.exports = {
  createGame,
  getGames
};
