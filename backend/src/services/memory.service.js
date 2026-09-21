const db = require('../db');

/**
 * Format raw gaming memory row into clean camelCase object
 * @param {Object} row 
 * @returns {Object}
 */
const formatMemory = (row) => {
  const memory = {
    id: row.id,
    title: row.title,
    summary: row.summary || null,
    memoryType: row.memory_type,
    sessionId: row.session_id || null,
    metadata: row.metadata || {},
    session: null,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };

  if (row.session_id) {
    memory.session = {
      id: row.session_id,
      gameId: row.game_id || null,
      gameName: row.game_name || null,
      platform: row.game_platform || null,
      startedAt: row.session_started_at || null,
      endedAt: row.session_ended_at || null,
      duration: row.session_duration !== null && row.session_duration !== undefined ? Number(row.session_duration) : null
    };
  }

  return memory;
};

/**
 * Create a new gaming memory
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const createMemory = async ({ userId, title, summary, memoryType, sessionId, metadata }) => {
  // 1. If sessionId is provided, verify it exists and belongs to the authenticated user
  if (sessionId) {
    const sessionCheck = await db.query(
      'SELECT id FROM gaming_sessions WHERE id = $1 AND user_id = $2;',
      [sessionId, userId]
    );

    if (sessionCheck.rows.length === 0) {
      const error = new Error('Gaming session not found');
      error.statusCode = 404;
      throw error;
    }
  }

  // 2. Prepare values
  const trimmedTitle = title.trim();
  const trimmedSummary = summary && typeof summary === 'string' ? summary.trim() : null;
  const trimmedMemoryType = memoryType.trim();
  const safeMetadata = metadata && typeof metadata === 'object' && !Array.isArray(metadata) ? metadata : {};
  const safeSessionId = sessionId || null;

  // 3. Insert memory
  const insertResult = await db.query(
    `INSERT INTO gaming_memories (user_id, session_id, title, summary, memory_type, metadata)
     VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING id, user_id, session_id, title, summary, memory_type, metadata, created_at, updated_at;`,
    [userId, safeSessionId, trimmedTitle, trimmedSummary, trimmedMemoryType, safeMetadata]
  );

  const inserted = insertResult.rows[0];

  // If attached to a session, fetch session & game details for response
  if (safeSessionId) {
    const sessionDetails = await db.query(
      `SELECT 
         s.game_id, s.started_at, s.ended_at, s.duration,
         g.name AS game_name, g.platform AS game_platform
       FROM gaming_sessions s
       JOIN games g ON g.id = s.game_id
       WHERE s.id = $1;`,
      [safeSessionId]
    );

    const sRow = sessionDetails.rows[0];
    return formatMemory({
      ...inserted,
      game_id: sRow?.game_id,
      game_name: sRow?.game_name,
      game_platform: sRow?.game_platform,
      session_started_at: sRow?.started_at,
      session_ended_at: sRow?.ended_at,
      session_duration: sRow?.duration
    });
  }

  return formatMemory(inserted);
};

/**
 * Retrieve paginated gaming memories with optional filtering
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getMemories = async ({ userId, page, limit, memoryType, sessionId }) => {
  const offset = (page - 1) * limit;

  // Build parameterized WHERE clauses
  const whereClauses = ['gm.user_id = $1'];
  const queryParams = [userId];
  let paramIndex = 2;

  if (memoryType && typeof memoryType === 'string' && memoryType.trim()) {
    whereClauses.push(`gm.memory_type = $${paramIndex++}`);
    queryParams.push(memoryType.trim());
  }

  if (sessionId) {
    whereClauses.push(`gm.session_id = $${paramIndex++}`);
    queryParams.push(sessionId);
  }

  const whereSql = whereClauses.join(' AND ');

  // 1. Total count
  const countResult = await db.query(
    `SELECT COUNT(*)::integer AS total FROM gaming_memories gm WHERE ${whereSql};`,
    queryParams
  );
  const total = countResult.rows[0].total;
  const totalPages = Math.ceil(total / limit);

  // 2. Fetch paginated memories with joined session and game info
  const listParams = [...queryParams, limit, offset];
  const listResult = await db.query(
    `SELECT 
       gm.id, gm.user_id, gm.session_id, gm.title, gm.summary, gm.memory_type, gm.metadata, gm.created_at, gm.updated_at,
       gs.game_id, gs.started_at AS session_started_at, gs.ended_at AS session_ended_at, gs.duration AS session_duration,
       g.name AS game_name, g.platform AS game_platform
     FROM gaming_memories gm
     LEFT JOIN gaming_sessions gs ON gs.id = gm.session_id
     LEFT JOIN games g ON g.id = gs.game_id
     WHERE ${whereSql}
     ORDER BY gm.created_at DESC
     LIMIT $${paramIndex++} OFFSET $${paramIndex++};`,
    listParams
  );

  return {
    memories: listResult.rows.map(formatMemory),
    pagination: {
      page,
      limit,
      total,
      totalPages
    }
  };
};

/**
 * Retrieve a single gaming memory by ID
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getMemoryById = async ({ memoryId, userId }) => {
  const result = await db.query(
    `SELECT 
       gm.id, gm.user_id, gm.session_id, gm.title, gm.summary, gm.memory_type, gm.metadata, gm.created_at, gm.updated_at,
       gs.game_id, gs.started_at AS session_started_at, gs.ended_at AS session_ended_at, gs.duration AS session_duration,
       g.name AS game_name, g.platform AS game_platform
     FROM gaming_memories gm
     LEFT JOIN gaming_sessions gs ON gs.id = gm.session_id
     LEFT JOIN games g ON g.id = gs.game_id
     WHERE gm.id = $1 AND gm.user_id = $2;`,
    [memoryId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Gaming memory not found');
    error.statusCode = 404;
    throw error;
  }

  return formatMemory(result.rows[0]);
};

/**
 * Update a gaming memory
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const updateMemory = async ({ memoryId, userId, updates }) => {
  // 1. Verify memory exists and belongs to user
  const checkResult = await db.query(
    'SELECT id, session_id FROM gaming_memories WHERE id = $1 AND user_id = $2;',
    [memoryId, userId]
  );

  if (checkResult.rows.length === 0) {
    const error = new Error('Gaming memory not found');
    error.statusCode = 404;
    throw error;
  }

  // 2. Build dynamic update query
  const setClauses = [];
  const queryParams = [memoryId, userId];
  let paramIndex = 3;

  if (updates.title !== undefined) {
    setClauses.push(`title = $${paramIndex++}`);
    queryParams.push(updates.title.trim());
  }

  if (updates.summary !== undefined) {
    setClauses.push(`summary = $${paramIndex++}`);
    queryParams.push(typeof updates.summary === 'string' ? updates.summary.trim() : null);
  }

  if (updates.memoryType !== undefined) {
    setClauses.push(`memory_type = $${paramIndex++}`);
    queryParams.push(updates.memoryType.trim());
  }

  if (updates.metadata !== undefined) {
    setClauses.push(`metadata = $${paramIndex++}`);
    queryParams.push(updates.metadata);
  }

  setClauses.push('updated_at = CURRENT_TIMESTAMP');

  const updateSql = `
    UPDATE gaming_memories
    SET ${setClauses.join(', ')}
    WHERE id = $1 AND user_id = $2
    RETURNING id, user_id, session_id, title, summary, memory_type, metadata, created_at, updated_at;
  `;

  const updateResult = await db.query(updateSql, queryParams);
  const updatedRow = updateResult.rows[0];

  // If attached to session, fetch session & game details
  if (updatedRow.session_id) {
    const sessionDetails = await db.query(
      `SELECT 
         s.game_id, s.started_at, s.ended_at, s.duration,
         g.name AS game_name, g.platform AS game_platform
       FROM gaming_sessions s
       JOIN games g ON g.id = s.game_id
       WHERE s.id = $1;`,
      [updatedRow.session_id]
    );

    const sRow = sessionDetails.rows[0];
    return formatMemory({
      ...updatedRow,
      game_id: sRow?.game_id,
      game_name: sRow?.game_name,
      game_platform: sRow?.game_platform,
      session_started_at: sRow?.started_at,
      session_ended_at: sRow?.ended_at,
      session_duration: sRow?.duration
    });
  }

  return formatMemory(updatedRow);
};

/**
 * Delete a gaming memory
 * @param {Object} param0 
 * @returns {Promise<void>}
 */
const deleteMemory = async ({ memoryId, userId }) => {
  const result = await db.query(
    'DELETE FROM gaming_memories WHERE id = $1 AND user_id = $2 RETURNING id;',
    [memoryId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Gaming memory not found');
    error.statusCode = 404;
    throw error;
  }
};

module.exports = {
  createMemory,
  getMemories,
  getMemoryById,
  updateMemory,
  deleteMemory
};
