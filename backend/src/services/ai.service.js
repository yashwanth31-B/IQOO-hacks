const db = require('../db');

/**
 * Service handling AI Context Retrieval and Provider Abstraction
 */

/**
 * Retrieve scoped user gaming context (Sessions, Memories, Tasks)
 * Strictly constrained to the authenticated user ID.
 * Never includes sensitive fields (password_hash, tokens, secrets).
 * 
 * @param {string} userId - Authenticated user UUID
 * @returns {Promise<{ user: Object, sessions: Array, memories: Array, tasks: Array }>}
 */
const getUserContext = async (userId) => {
  // 1. Verify and fetch user basic info
  const userResult = await db.query(
    'SELECT id, name, email, created_at FROM users WHERE id = $1',
    [userId]
  );

  if (userResult.rows.length === 0) {
    const error = new Error('User not found');
    error.statusCode = 404;
    throw error;
  }

  const userRow = userResult.rows[0];

  // 2. Fetch recent gaming sessions with game metadata
  const sessionsResult = await db.query(
    `SELECT 
      s.id,
      s.game_id,
      g.name AS game_name,
      g.platform,
      s.started_at,
      s.ended_at,
      s.duration,
      s.score,
      s.performance,
      s.notes,
      s.created_at
    FROM gaming_sessions s
    LEFT JOIN games g ON s.game_id = g.id
    WHERE s.user_id = $1
    ORDER BY s.started_at DESC
    LIMIT 10`,
    [userId]
  );

  const sessions = sessionsResult.rows.map((row) => ({
    id: row.id,
    gameId: row.game_id,
    gameName: row.game_name || 'Unknown Game',
    platform: row.platform || null,
    startedAt: row.started_at,
    endedAt: row.ended_at,
    duration: row.duration !== null ? Number(row.duration) : null,
    score: row.score !== null ? Number(row.score) : null,
    performance: row.performance || null,
    notes: row.notes || null,
    createdAt: row.created_at
  }));

  // 3. Fetch recent gaming memories with linked session metadata
  const memoriesResult = await db.query(
    `SELECT 
      m.id,
      m.title,
      m.summary,
      m.memory_type,
      m.metadata,
      m.session_id,
      g.name AS game_name,
      m.created_at
    FROM gaming_memories m
    LEFT JOIN gaming_sessions s ON m.session_id = s.id
    LEFT JOIN games g ON s.game_id = g.id
    WHERE m.user_id = $1
    ORDER BY m.created_at DESC
    LIMIT 10`,
    [userId]
  );

  const memories = memoriesResult.rows.map((row) => ({
    id: row.id,
    title: row.title,
    summary: row.summary || null,
    memoryType: row.memory_type,
    metadata: row.metadata || {},
    sessionId: row.session_id || null,
    gameName: row.game_name || null,
    createdAt: row.created_at
  }));

  // 4. Fetch productivity tasks
  const tasksResult = await db.query(
    `SELECT 
      id,
      title,
      description,
      priority,
      due_date,
      estimated_minutes,
      completed,
      created_at
    FROM tasks
    WHERE user_id = $1
    ORDER BY created_at DESC
    LIMIT 10`,
    [userId]
  );

  const tasks = tasksResult.rows.map((row) => ({
    id: row.id,
    title: row.title,
    description: row.description || null,
    priority: row.priority,
    dueDate: row.due_date,
    estimatedMinutes: row.estimated_minutes,
    completed: row.completed,
    createdAt: row.created_at
  }));

  return {
    user: {
      id: userRow.id,
      name: userRow.name
    },
    sessions,
    memories,
    tasks
  };
};

/**
 * Synthesize a development response when external AI provider is unconfigured.
 * Answers common context queries factually from the user's Second Brain,
 * while clearly stating development status.
 * 
 * @param {string} message 
 * @param {Object} context 
 * @returns {string}
 */
const generateDevelopmentResponse = (message, context) => {
  const lower = message.toLowerCase();

  // Query: Highest score or best performance
  if ((lower.includes('best') || lower.includes('highest') || lower.includes('strongest')) && context.sessions.length > 0) {
    const scored = context.sessions.filter((s) => s.score !== null);
    if (scored.length > 0) {
      const best = scored.reduce((max, s) => (s.score > max.score ? s : max), scored[0]);
      const sessionDate = new Date(best.startedAt).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
      return `Your strongest recorded session was your ${best.gameName} session on ${sessionDate} with a score of ${best.score}${
        best.performance ? ` and rating "${best.performance}"` : ''
      }.\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
    }
  }

  // Query: Last gaming session
  if ((lower.includes('last') || lower.includes('recent')) && context.sessions.length > 0) {
    const last = context.sessions[0];
    const sessionDate = new Date(last.startedAt).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
    return `Your most recent recorded session was ${last.gameName}${
      last.platform ? ` on ${last.platform}` : ''
    } played on ${sessionDate}${
      last.duration ? ` (${Math.round(last.duration / 60)} minutes)` : ''
    }.\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
  }

  // Query: Tasks or pending tasks
  if ((lower.includes('task') || lower.includes('pending')) && context.tasks.length > 0) {
    const pending = context.tasks.filter((t) => !t.completed);
    if (pending.length > 0) {
      const list = pending.slice(0, 5).map((t) => `• ${t.title} [${t.priority}]`).join('\n');
      return `You have ${pending.length} pending task(s):\n${list}\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
    }
    return `All your tasks are currently marked completed!\n\n(AI service is in development mode.)`;
  }

  // Query: Total gaming time logged
  if ((lower.includes('how much') || lower.includes('time') || lower.includes('spent') || lower.includes('gamed')) && context.sessions.length > 0) {
    const totalSeconds = context.sessions.reduce((acc, s) => acc + (s.duration || 0), 0);
    const totalMinutes = Math.round(totalSeconds / 60);
    return `You have logged approximately ${totalMinutes} minute(s) across your ${context.sessions.length} most recent recorded gaming session(s).\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
  }

  // Default transparent response
  return 'AI service is not configured yet. The Copilot interface is ready for AI integration.';
};

/**
 * Pluggable AI Provider Adapter
 * 
 * Supports external provider configuration via environment variables
 * (AI_PROVIDER, AI_API_KEY, AI_MODEL) with fallback to development adapter.
 * 
 * @param {string} message - User message
 * @param {Object} context - User gaming context
 * @returns {Promise<{ message: string, sources: Object, provider: string }>}
 */
const generateResponse = async (message, context) => {
  const provider = process.env.AI_PROVIDER || 'development';
  const apiKey = process.env.AI_API_KEY;

  // Build clean sources summary to return with the response
  const sources = {
    sessions: context.sessions.map((s) => ({
      id: s.id,
      gameName: s.gameName,
      platform: s.platform,
      startedAt: s.startedAt,
      score: s.score,
      performance: s.performance
    })),
    memories: context.memories.map((m) => ({
      id: m.id,
      title: m.title,
      memoryType: m.memoryType,
      gameName: m.gameName
    })),
    tasks: context.tasks.map((t) => ({
      id: t.id,
      title: t.title,
      priority: t.priority,
      completed: t.completed
    }))
  };

  // If no external API key is configured or provider is development
  if (!apiKey || provider === 'development') {
    const reply = generateDevelopmentResponse(message, context);
    return {
      message: reply,
      sources,
      provider: 'development'
    };
  }

  // If external provider is configured, handle securely
  try {
    // In future steps, external provider clients (e.g. Gemini, OpenAI) plug in here.
    // For now, if an unhandled provider is specified:
    const reply = generateDevelopmentResponse(message, context);
    return {
      message: reply,
      sources,
      provider
    };
  } catch (providerError) {
    // Safe fallback if provider fails
    return {
      message: 'AI service is not configured yet. The Copilot interface is ready for AI integration.',
      sources,
      provider: 'development'
    };
  }
};

/**
 * Process chat interaction: retrieve context and generate response
 * 
 * @param {Object} param0 
 * @param {string} param0.userId - Authenticated user UUID
 * @param {string} param0.message - User query
 * @returns {Promise<{ message: string, sources: Object, provider: string }>}
 */
const processChat = async ({ userId, message }) => {
  const context = await getUserContext(userId);
  const result = await generateResponse(message, context);
  return result;
};

module.exports = {
  getUserContext,
  generateResponse,
  processChat
};
