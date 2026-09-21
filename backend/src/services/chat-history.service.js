const db = require('../db');
const { isValidUUID } = require('../utils/validation.utils');

/**
 * Deterministically generate a conversation title from the first message
 * without making external AI API requests. Capped safely under 255 chars.
 * 
 * @param {string} message 
 * @returns {string}
 */
const generateConversationTitle = (message) => {
  if (!message || typeof message !== 'string') return 'New Conversation';
  const clean = message.trim().replace(/[^\w\s-]/g, ' ').replace(/\s+/g, ' ');
  if (!clean) return 'New Conversation';

  const lower = clean.toLowerCase();

  // Pattern-based topic extraction
  if (lower.includes('best') || lower.includes('highest score') || lower.includes('perform best')) {
    const match = clean.match(/(?:in|at|for|on)\s+([A-Za-z0-9\s]+)/i);
    if (match && match[1]?.trim()) {
      const game = match[1].trim().split(' ').slice(0, 3).join(' ');
      return `${capitalizeWords(game)} Performance`;
    }
    return 'Performance Analysis';
  }

  if (lower.includes('last session') || lower.includes('recent session') || lower.includes('last game')) {
    const match = clean.match(/(?:in|at|for|on)\s+([A-Za-z0-9\s]+)/i);
    if (match && match[1]?.trim()) {
      const game = match[1].trim().split(' ').slice(0, 3).join(' ');
      return `${capitalizeWords(game)} Recent Session`;
    }
    return 'Recent Gaming Session';
  }

  if (lower.includes('task') || lower.includes('pending') || lower.includes('todo')) {
    return 'Pending Tasks';
  }

  if (lower.includes('how much') || lower.includes('time') || lower.includes('gamed')) {
    return 'Gaming Time Overview';
  }

  // Strip common conversational filler prefixes
  const prefixes = [
    /^tell me about my\s+/i,
    /^tell me about\s+/i,
    /^what are my\s+/i,
    /^what is my\s+/i,
    /^can you tell me about\s+/i,
    /^can you summarize\s+/i,
    /^summarize my\s+/i,
    /^what do you know about\s+/i
  ];

  let topic = clean;
  for (const prefix of prefixes) {
    if (prefix.test(topic)) {
      topic = topic.replace(prefix, '').trim();
      break;
    }
  }

  const words = topic.split(' ').filter(Boolean).slice(0, 6);
  if (words.length === 0) return 'New Conversation';

  let title = capitalizeWords(words.join(' '));
  if (title.length > 60) {
    title = title.slice(0, 57).trim() + '...';
  }
  return title;
};

const capitalizeWords = (str) => {
  return str
    .split(' ')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
};

/**
 * Format conversation row to camelCase
 */
const formatConversation = (row) => ({
  id: row.id,
  userId: row.user_id,
  title: row.title || 'New Conversation',
  createdAt: row.created_at,
  updatedAt: row.updated_at,
  messageCount: row.message_count !== undefined ? Number(row.message_count) : undefined
});

/**
 * Format message row to camelCase
 */
const formatMessage = (row) => ({
  id: row.id,
  conversationId: row.conversation_id,
  role: row.role,
  content: row.content,
  provider: row.provider || null,
  sources: row.sources || {},
  createdAt: row.created_at
});

/**
 * Create a new conversation for an authenticated user
 * 
 * @param {Object} param0 
 * @param {string} param0.userId - Authenticated user UUID
 * @param {string} [param0.title] - Optional title
 * @returns {Promise<Object>}
 */
const createConversation = async ({ userId, title = null }) => {
  const safeTitle = (title && typeof title === 'string' && title.trim().slice(0, 255)) || 'New Conversation';

  const result = await db.query(
    `INSERT INTO ai_conversations (user_id, title)
     VALUES ($1, $2)
     RETURNING id, user_id, title, created_at, updated_at`,
    [userId, safeTitle]
  );

  return formatConversation(result.rows[0]);
};

/**
 * Verify conversation ownership strictly using req.user.id
 * Returns conversation if owned, or throws a 404 Error (safe IDOR protection)
 * 
 * @param {string} conversationId - UUID
 * @param {string} userId - Authenticated user UUID
 * @returns {Promise<Object>}
 */
const verifyConversationOwnership = async (conversationId, userId) => {
  if (!isValidUUID(conversationId)) {
    const err = new Error('Invalid conversation ID format: must be a valid UUID');
    err.statusCode = 400;
    throw err;
  }

  const result = await db.query(
    `SELECT id, user_id, title, created_at, updated_at
     FROM ai_conversations
     WHERE id = $1`,
    [conversationId]
  );

  if (result.rows.length === 0) {
    const err = new Error('Conversation not found');
    err.statusCode = 404;
    throw err;
  }

  const row = result.rows[0];

  // Strictly enforce user ownership; do not leak existence of another user's conversation
  if (row.user_id !== userId) {
    const err = new Error('Conversation not found');
    err.statusCode = 404;
    throw err;
  }

  return formatConversation(row);
};

/**
 * Save user message to database
 * 
 * @param {Object} param0 
 * @param {string} param0.conversationId 
 * @param {string} param0.content 
 * @returns {Promise<Object>}
 */
const saveUserMessage = async ({ conversationId, content }) => {
  const msgResult = await db.query(
    `INSERT INTO ai_messages (conversation_id, role, content, provider, sources)
     VALUES ($1, 'user', $2, NULL, '{}'::jsonb)
     RETURNING id, conversation_id, role, content, provider, sources, created_at`,
    [conversationId, content]
  );

  await db.query(
    `UPDATE ai_conversations
     SET updated_at = CURRENT_TIMESTAMP
     WHERE id = $1`,
    [conversationId]
  );

  return formatMessage(msgResult.rows[0]);
};

/**
 * Save assistant message to database
 * 
 * @param {Object} param0 
 * @param {string} param0.conversationId 
 * @param {string} param0.content 
 * @param {string} [param0.provider] 
 * @param {Object} [param0.sources] 
 * @returns {Promise<Object>}
 */
const saveAssistantMessage = async ({ conversationId, content, provider = 'development', sources = {} }) => {
  const safeSources = typeof sources === 'object' && sources !== null ? sources : {};

  const msgResult = await db.query(
    `INSERT INTO ai_messages (conversation_id, role, content, provider, sources)
     VALUES ($1, 'assistant', $2, $3, $4)
     RETURNING id, conversation_id, role, content, provider, sources, created_at`,
    [conversationId, content, provider, JSON.stringify(safeSources)]
  );

  await db.query(
    `UPDATE ai_conversations
     SET updated_at = CURRENT_TIMESTAMP
     WHERE id = $1`,
    [conversationId]
  );

  return formatMessage(msgResult.rows[0]);
};

/**
 * Retrieve a conversation and its messages
 * 
 * @param {string} conversationId 
 * @param {string} userId 
 * @returns {Promise<Object>}
 */
const getConversation = async (conversationId, userId) => {
  const conversation = await verifyConversationOwnership(conversationId, userId);

  const messagesResult = await db.query(
    `SELECT id, conversation_id, role, content, provider, sources, created_at
     FROM ai_messages
     WHERE conversation_id = $1
     ORDER BY created_at ASC`,
    [conversationId]
  );

  return {
    ...conversation,
    messages: messagesResult.rows.map(formatMessage)
  };
};

/**
 * Retrieve bounded recent messages for context feeding to AI provider
 * 
 * @param {string} conversationId 
 * @param {string} userId 
 * @param {number} [limit=15] 
 * @returns {Promise<Array>}
 */
const getRecentConversationMessages = async (conversationId, userId, limit = 15) => {
  await verifyConversationOwnership(conversationId, userId);

  const safeLimit = Math.min(Math.max(Number(limit) || 15, 1), 50);

  const result = await db.query(
    `SELECT id, conversation_id, role, content, provider, sources, created_at
     FROM (
       SELECT id, conversation_id, role, content, provider, sources, created_at
       FROM ai_messages
       WHERE conversation_id = $1
       ORDER BY created_at DESC
       LIMIT $2
     ) sub
     ORDER BY created_at ASC`,
    [conversationId, safeLimit]
  );

  return result.rows.map(formatMessage);
};

/**
 * List conversations belonging to the authenticated user with pagination
 * 
 * @param {string} userId 
 * @param {Object} [pagination] 
 * @returns {Promise<{ conversations: Array, pagination: Object }>}
 */
const listUserConversations = async (userId, { page = 1, limit = 20 } = {}) => {
  const parsedPage = Math.max(parseInt(page, 10) || 1, 1);
  const parsedLimit = Math.min(Math.max(parseInt(limit, 10) || 20, 1), 100);
  const offset = (parsedPage - 1) * parsedLimit;

  const countResult = await db.query(
    `SELECT COUNT(*)::int AS total FROM ai_conversations WHERE user_id = $1`,
    [userId]
  );
  const total = countResult.rows[0].total;

  const listResult = await db.query(
    `SELECT 
       c.id, 
       c.user_id, 
       c.title, 
       c.created_at, 
       c.updated_at,
       COUNT(m.id)::int AS message_count
     FROM ai_conversations c
     LEFT JOIN ai_messages m ON c.id = m.conversation_id
     WHERE c.user_id = $1
     GROUP BY c.id
     ORDER BY c.updated_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, parsedLimit, offset]
  );

  return {
    conversations: listResult.rows.map(formatConversation),
    pagination: {
      total,
      page: parsedPage,
      limit: parsedLimit,
      totalPages: Math.ceil(total / parsedLimit) || 1
    }
  };
};

/**
 * Delete a user's conversation (and cascading messages)
 * 
 * @param {string} conversationId 
 * @param {string} userId 
 * @returns {Promise<{ id: string }>}
 */
const deleteUserConversation = async (conversationId, userId) => {
  await verifyConversationOwnership(conversationId, userId);

  await db.query(
    `DELETE FROM ai_conversations WHERE id = $1 AND user_id = $2`,
    [conversationId, userId]
  );

  return { id: conversationId };
};

module.exports = {
  generateConversationTitle,
  createConversation,
  verifyConversationOwnership,
  saveUserMessage,
  saveAssistantMessage,
  getConversation,
  getRecentConversationMessages,
  listUserConversations,
  deleteUserConversation
};
