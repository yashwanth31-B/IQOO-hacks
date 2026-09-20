const db = require('../db');

/**
 * Format raw gaming session row into a clean camelCase object
 * @param {Object} row 
 * @returns {Object}
 */
const formatSession = (row) => ({
  id: row.id,
  gameId: row.game_id,
  gameName: row.game_name || null,
  platform: row.game_platform !== undefined ? row.game_platform : (row.platform || null),
  startedAt: row.started_at,
  endedAt: row.ended_at,
  duration: row.duration !== null ? Number(row.duration) : null,
  score: row.score !== null && row.score !== undefined ? Number(row.score) : null,
  performance: row.performance || null,
  notes: row.notes || null,
  createdAt: row.created_at,
  updatedAt: row.updated_at
});

/**
 * Start a new gaming session
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const createSession = async ({ userId, gameId, score, performance, notes }) => {
  // 1. Verify game exists
  const gameResult = await db.query(
    'SELECT id, name, platform FROM games WHERE id = $1;',
    [gameId]
  );

  if (gameResult.rows.length === 0) {
    const error = new Error('Game not found');
    error.statusCode = 404;
    throw error;
  }

  const game = gameResult.rows[0];

  // 2. Check if user already has an active session
  const activeCheck = await db.query(
    'SELECT id FROM gaming_sessions WHERE user_id = $1 AND ended_at IS NULL LIMIT 1;',
    [userId]
  );

  if (activeCheck.rows.length > 0) {
    const error = new Error('An active gaming session already exists');
    error.statusCode = 409;
    throw error;
  }

  // 3. Insert session
  const parsedScore = score !== undefined && score !== null ? Number(score) : null;
  const trimmedPerformance = performance && typeof performance === 'string' ? performance.trim() : null;
  const trimmedNotes = notes && typeof notes === 'string' ? notes.trim() : null;

  const insertResult = await db.query(
    `INSERT INTO gaming_sessions (user_id, game_id, score, performance, notes)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING id, user_id, game_id, started_at, ended_at, duration, score, performance, notes, created_at, updated_at;`,
    [userId, gameId, parsedScore, trimmedPerformance, trimmedNotes]
  );

  const newSession = insertResult.rows[0];
  return formatSession({
    ...newSession,
    game_name: game.name,
    game_platform: game.platform
  });
};

/**
 * Retrieve user's currently active gaming session
 * @param {string} userId 
 * @returns {Promise<Object|null>}
 */
const getActiveSession = async (userId) => {
  const result = await db.query(
    `SELECT 
       s.id, s.user_id, s.game_id, s.started_at, s.ended_at, s.duration, 
       s.score, s.performance, s.notes, s.created_at, s.updated_at,
       g.name AS game_name, g.platform AS game_platform
     FROM gaming_sessions s
     JOIN games g ON g.id = s.game_id
     WHERE s.user_id = $1 AND s.ended_at IS NULL
     LIMIT 1;`,
    [userId]
  );

  if (result.rows.length === 0) {
    return null;
  }

  return formatSession(result.rows[0]);
};

/**
 * Retrieve single gaming session belonging to authenticated user
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getSessionById = async ({ sessionId, userId }) => {
  const result = await db.query(
    `SELECT 
       s.id, s.user_id, s.game_id, s.started_at, s.ended_at, s.duration, 
       s.score, s.performance, s.notes, s.created_at, s.updated_at,
       g.name AS game_name, g.platform AS game_platform
     FROM gaming_sessions s
     JOIN games g ON g.id = s.game_id
     WHERE s.id = $1 AND s.user_id = $2;`,
    [sessionId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Gaming session not found');
    error.statusCode = 404;
    throw error;
  }

  return formatSession(result.rows[0]);
};

/**
 * Retrieve paginated gaming sessions belonging to authenticated user
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getUserSessions = async ({ userId, page, limit }) => {
  const offset = (page - 1) * limit;

  // 1. Get total count
  const countResult = await db.query(
    'SELECT COUNT(*)::integer AS total FROM gaming_sessions WHERE user_id = $1;',
    [userId]
  );
  const total = countResult.rows[0].total;
  const totalPages = Math.ceil(total / limit);

  // 2. Fetch paginated records
  const result = await db.query(
    `SELECT 
       s.id, s.user_id, s.game_id, s.started_at, s.ended_at, s.duration, 
       s.score, s.performance, s.notes, s.created_at, s.updated_at,
       g.name AS game_name, g.platform AS game_platform
     FROM gaming_sessions s
     JOIN games g ON g.id = s.game_id
     WHERE s.user_id = $1
     ORDER BY s.started_at DESC
     LIMIT $2 OFFSET $3;`,
    [userId, limit, offset]
  );

  return {
    sessions: result.rows.map(formatSession),
    pagination: {
      page,
      limit,
      total,
      totalPages
    }
  };
};

/**
 * Update gaming session details (score, performance, notes)
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const updateSession = async ({ sessionId, userId, updates }) => {
  // First verify session ownership
  const checkResult = await db.query(
    'SELECT id, game_id FROM gaming_sessions WHERE id = $1 AND user_id = $2;',
    [sessionId, userId]
  );

  if (checkResult.rows.length === 0) {
    const error = new Error('Gaming session not found');
    error.statusCode = 404;
    throw error;
  }

  // Build dynamic update query
  const setClauses = [];
  const queryParams = [sessionId, userId];
  let paramIndex = 3;

  if (updates.score !== undefined) {
    setClauses.push(`score = $${paramIndex++}`);
    queryParams.push(updates.score !== null ? Number(updates.score) : null);
  }

  if (updates.performance !== undefined) {
    setClauses.push(`performance = $${paramIndex++}`);
    queryParams.push(typeof updates.performance === 'string' ? updates.performance.trim() : null);
  }

  if (updates.notes !== undefined) {
    setClauses.push(`notes = $${paramIndex++}`);
    queryParams.push(typeof updates.notes === 'string' ? updates.notes.trim() : null);
  }

  setClauses.push('updated_at = CURRENT_TIMESTAMP');

  const updateSql = `
    UPDATE gaming_sessions
    SET ${setClauses.join(', ')}
    WHERE id = $1 AND user_id = $2
    RETURNING id, user_id, game_id, started_at, ended_at, duration, score, performance, notes, created_at, updated_at;
  `;

  const updateResult = await db.query(updateSql, queryParams);
  const updatedRow = updateResult.rows[0];

  // Fetch game info for consistent response
  const gameResult = await db.query(
    'SELECT name, platform FROM games WHERE id = $1;',
    [updatedRow.game_id]
  );

  const game = gameResult.rows[0] || {};
  return formatSession({
    ...updatedRow,
    game_name: game.name,
    game_platform: game.platform
  });
};

/**
 * End an active gaming session with PostgreSQL duration calculation
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const endSession = async ({ sessionId, userId }) => {
  // 1. Check if session exists and belongs to user
  const checkResult = await db.query(
    'SELECT id, started_at, ended_at, game_id FROM gaming_sessions WHERE id = $1 AND user_id = $2;',
    [sessionId, userId]
  );

  if (checkResult.rows.length === 0) {
    const error = new Error('Gaming session not found');
    error.statusCode = 404;
    throw error;
  }

  const existing = checkResult.rows[0];

  // 2. Reject if already ended
  if (existing.ended_at !== null) {
    const error = new Error('Gaming session has already ended');
    error.statusCode = 409;
    throw error;
  }

  // 3. End session and calculate duration in seconds using PostgreSQL epoch extraction
  const updateResult = await db.query(
    `UPDATE gaming_sessions
     SET ended_at = CURRENT_TIMESTAMP,
         duration = GREATEST(0, ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))))::integer,
         updated_at = CURRENT_TIMESTAMP
     WHERE id = $1 AND user_id = $2
     RETURNING id, user_id, game_id, started_at, ended_at, duration, score, performance, notes, created_at, updated_at;`,
    [sessionId, userId]
  );

  const endedRow = updateResult.rows[0];

  // Fetch game details
  const gameResult = await db.query(
    'SELECT name, platform FROM games WHERE id = $1;',
    [endedRow.game_id]
  );

  const game = gameResult.rows[0] || {};
  return formatSession({
    ...endedRow,
    game_name: game.name,
    game_platform: game.platform
  });
};

/**
 * Delete a gaming session belonging to authenticated user
 * @param {Object} param0 
 * @returns {Promise<void>}
 */
const deleteSession = async ({ sessionId, userId }) => {
  const result = await db.query(
    'DELETE FROM gaming_sessions WHERE id = $1 AND user_id = $2 RETURNING id;',
    [sessionId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Gaming session not found');
    error.statusCode = 404;
    throw error;
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
