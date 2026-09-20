const db = require('../db');

/**
 * Format a raw games row into a clean camelCase object
 * @param {Object} row 
 * @returns {Object}
 */
const formatGame = (row) => ({
  id: row.id,
  name: row.name,
  platform: row.platform,
  createdAt: row.created_at
});

/**
 * Create a new game in the catalog
 * @param {Object} param0 
 * @param {string} param0.name
 * @param {string} [param0.platform]
 * @returns {Promise<Object>}
 */
const createGame = async ({ name, platform }) => {
  const trimmedName = name.trim();
  const trimmedPlatform = platform && typeof platform === 'string' ? platform.trim() : null;

  const result = await db.query(
    `INSERT INTO games (name, platform)
     VALUES ($1, $2)
     RETURNING id, name, platform, created_at;`,
    [trimmedName, trimmedPlatform]
  );

  return formatGame(result.rows[0]);
};

/**
 * Get all available games
 * @returns {Promise<Array<Object>>}
 */
const getAllGames = async () => {
  const result = await db.query(
    'SELECT id, name, platform, created_at FROM games ORDER BY name ASC;'
  );

  return result.rows.map(formatGame);
};

/**
 * Find game by UUID
 * @param {string} gameId 
 * @returns {Promise<Object|null>}
 */
const getGameById = async (gameId) => {
  const result = await db.query(
    'SELECT id, name, platform, created_at FROM games WHERE id = $1;',
    [gameId]
  );

  if (result.rows.length === 0) {
    return null;
  }

  return formatGame(result.rows[0]);
};

module.exports = {
  createGame,
  getAllGames,
  getGameById
};
