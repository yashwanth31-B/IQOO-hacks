const db = require('../db');
const { GoogleGenerativeAI } = require('@google/generative-ai');

/**
 * Service handling AI Context Retrieval, Intelligent Context Selection,
 * and Google Gemini / Development Provider Integration
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
    LIMIT 20`,
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
    LIMIT 20`,
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
    LIMIT 20`,
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
 * Intelligent Context Selection
 * 
 * Filters and prioritizes relevant Second Brain records according to the
 * user's question, while bounding prompt size to maintain fast, efficient inference.
 * 
 * @param {string} message - User query
 * @param {Object} fullContext - Full user context
 * @returns {Object} Controlled, prioritized context
 */
const selectIntelligentContext = (message, fullContext) => {
  const lower = (message || '').toLowerCase();
  const { user, sessions, memories, tasks } = fullContext;

  let prioritizedSessions = [...sessions];
  let prioritizedMemories = [...memories];
  let prioritizedTasks = [...tasks];

  // 1. Detect query intent
  const isPerformanceQuery =
    lower.includes('best') ||
    lower.includes('highest') ||
    lower.includes('strongest') ||
    lower.includes('score') ||
    lower.includes('performance') ||
    lower.includes('mvp') ||
    lower.includes('clutch');

  const isRecencyQuery =
    lower.includes('last') ||
    lower.includes('recent') ||
    lower.includes('latest') ||
    lower.includes('today') ||
    lower.includes('yesterday');

  const isTaskQuery =
    lower.includes('task') ||
    lower.includes('pending') ||
    lower.includes('todo') ||
    lower.includes('due') ||
    lower.includes('homework') ||
    lower.includes('study') ||
    lower.includes('work');

  // 2. Check for game-specific mentions
  const allGameNames = [...new Set(sessions.map((s) => s.gameName).filter(Boolean))];
  const matchedGameName = allGameNames.find((name) => lower.includes(name.toLowerCase()));

  if (matchedGameName) {
    // Prioritize sessions and memories matching the requested game title
    const matchLower = matchedGameName.toLowerCase();
    prioritizedSessions.sort((a, b) => {
      const aMatch = a.gameName && a.gameName.toLowerCase() === matchLower ? 1 : 0;
      const bMatch = b.gameName && b.gameName.toLowerCase() === matchLower ? 1 : 0;
      return bMatch - aMatch;
    });

    prioritizedMemories.sort((a, b) => {
      const aMatch =
        (a.gameName && a.gameName.toLowerCase() === matchLower) ||
        (a.title && a.title.toLowerCase().includes(matchLower))
          ? 1
          : 0;
      const bMatch =
        (b.gameName && b.gameName.toLowerCase() === matchLower) ||
        (b.title && b.title.toLowerCase().includes(matchLower))
          ? 1
          : 0;
      return bMatch - aMatch;
    });
  } else if (isPerformanceQuery) {
    // Sort sessions by score descending (null scores at the end)
    prioritizedSessions.sort((a, b) => (b.score || 0) - (a.score || 0));
    // Prioritize highlights
    prioritizedMemories.sort((a, b) => (b.memoryType === 'highlight' ? 1 : 0) - (a.memoryType === 'highlight' ? 1 : 0));
  } else if (isRecencyQuery) {
    // Sort sessions by startedAt descending
    prioritizedSessions.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));
  } else if (isTaskQuery) {
    // Prioritize incomplete tasks and higher priority
    const prioWeight = { high: 3, medium: 2, low: 1 };
    prioritizedTasks.sort((a, b) => {
      if (a.completed !== b.completed) return a.completed ? 1 : -1;
      return (prioWeight[b.priority] || 0) - (prioWeight[a.priority] || 0);
    });
  }

  // 3. Enforce sensible limits to avoid oversized prompts
  const boundedSessions = prioritizedSessions.slice(0, 6).map((s) => ({
    id: s.id,
    gameName: s.gameName,
    platform: s.platform,
    startedAt: s.startedAt,
    endedAt: s.endedAt,
    duration: s.duration,
    score: s.score,
    performance: s.performance,
    notes: s.notes ? s.notes.slice(0, 250) : null
  }));

  const boundedMemories = prioritizedMemories.slice(0, 6).map((m) => ({
    id: m.id,
    title: m.title,
    summary: m.summary ? m.summary.slice(0, 250) : null,
    memoryType: m.memoryType,
    gameName: m.gameName,
    createdAt: m.createdAt
  }));

  const boundedTasks = prioritizedTasks.slice(0, 6).map((t) => ({
    id: t.id,
    title: t.title,
    description: t.description ? t.description.slice(0, 150) : null,
    priority: t.priority,
    dueDate: t.dueDate,
    estimatedMinutes: t.estimatedMinutes,
    completed: t.completed
  }));

  return {
    user,
    sessions: boundedSessions,
    memories: boundedMemories,
    tasks: boundedTasks
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
  if (
    (lower.includes('best') || lower.includes('highest') || lower.includes('strongest') || lower.includes('score')) &&
    context.sessions.length > 0
  ) {
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
  if (
    (lower.includes('how much') || lower.includes('time') || lower.includes('spent') || lower.includes('gamed')) &&
    context.sessions.length > 0
  ) {
    const totalSeconds = context.sessions.reduce((acc, s) => acc + (s.duration || 0), 0);
    const totalMinutes = Math.round(totalSeconds / 60);
    return `You have logged approximately ${totalMinutes} minute(s) across your ${context.sessions.length} most recent recorded gaming session(s).\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
  }

  // Default transparent response
  return 'AI service is not configured yet. The Copilot interface is ready for AI integration.';
};

const chatHistoryService = require('./chat-history.service');

/**
 * Generate completion using Google Gemini SDK
 * 
 * @param {string} message - User question
 * @param {Object} context - Selected intelligent Second Brain context
 * @param {Array} [history=[]] - Bounded recent conversation history
 * @returns {Promise<{ message: string, insights: Array<string>, referencedSourceIds: Object }>}
 */
const generateGeminiCompletion = async (message, context, history = []) => {
  const apiKey = process.env.AI_API_KEY;
  if (!apiKey) {
    throw new Error('AI_API_KEY is not configured');
  }

  const modelName = process.env.AI_MODEL || 'gemini-1.5-flash';
  const genAI = new GoogleGenerativeAI(apiKey);

  const systemInstruction = `You are AI Gaming Copilot, an intelligent gaming assistant and Second Brain companion.
You help the user understand their gaming journey based SOLELY on the supplied Second Brain records.

STRICT OPERATIONAL RULES:
1. Base all statements strictly on the provided Second Brain records (Sessions, Memories, Tasks).
2. DO NOT invent or hallucinate sessions, games, scores, durations, dates, performance ratings, memories, or tasks.
3. If the supplied records do not contain sufficient information to answer the question, clearly and politely state that the available Second Brain records do not contain that information. Never guess.
4. Distinguish recorded facts (such as scores, recorded durations, dates) from interpretations or general gameplay advice.
5. When comparing sessions or evaluating performance, cite the specific recorded metrics (e.g. score, performance rating, duration) supporting your conclusion.
6. Use recent conversation history for conversational context (e.g. follow-up questions or pronouns), but never let conversation history override factual Second Brain records.
7. Keep responses concise, actionable, and gamer-oriented.
8. Return your response strictly as a valid JSON object matching this schema:
{
  "message": "Direct, natural language response to the user's inquiry.",
  "insights": ["Concise observation, lesson, or actionable tip based on their data"],
  "referencedSourceIds": {
    "sessionIds": ["uuid-of-referenced-session"],
    "memoryIds": ["uuid-of-referenced-memory"],
    "taskIds": ["uuid-of-referenced-task"]
  }
}`;

  const formattedHistory = Array.isArray(history) && history.length > 0
    ? history.slice(-15).map((m) => `[${m.role === 'user' ? 'User' : 'Assistant'}]: ${m.content}`).join('\n')
    : 'None (new conversation)';

  const prompt = `CONVERSATION HISTORY:
${formattedHistory}

CURRENT USER QUESTION: "${message}"

USER SECOND BRAIN RECORDS:
User Profile: ${context.user.name} (ID: ${context.user.id})
Sessions: ${JSON.stringify(context.sessions, null, 2)}
Memories: ${JSON.stringify(context.memories, null, 2)}
Tasks: ${JSON.stringify(context.tasks, null, 2)}

Provide your response strictly in the specified JSON format.`;

  const model = genAI.getGenerativeModel({
    model: modelName,
    systemInstruction,
    generationConfig: {
      responseMimeType: 'application/json',
      temperature: 0.2
    }
  });

  // Timeout safety: 15 seconds max
  let timer;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('Gemini request timed out')), 15000);
  });

  try {
    const generatePromise = model.generateContent(prompt);
    const result = await Promise.race([generatePromise, timeoutPromise]);
    clearTimeout(timer);

    const responseText = result.response.text();
    let parsed;
    try {
      parsed = JSON.parse(responseText);
    } catch {
      // Strip markdown code fences if model wrapped response
      const cleaned = responseText.replace(/```json/gi, '').replace(/```/g, '').trim();
      parsed = JSON.parse(cleaned);
    }

    return parsed;
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
};

/**
 * Build sources summary strictly from the user's own context records
 * 
 * @param {Object} context 
 * @param {Object} [referencedIds] 
 * @returns {Object} Clean sources summary
 */
const buildSources = (context, referencedIds = null) => {
  let matchedSessions = context.sessions;
  let matchedMemories = context.memories;
  let matchedTasks = context.tasks;

  if (referencedIds) {
    const sIds = new Set(referencedIds.sessionIds || []);
    const mIds = new Set(referencedIds.memoryIds || []);
    const tIds = new Set(referencedIds.taskIds || []);

    if (sIds.size > 0) {
      matchedSessions = context.sessions.filter((s) => sIds.has(s.id));
    }
    if (mIds.size > 0) {
      matchedMemories = context.memories.filter((m) => mIds.has(m.id));
    }
    if (tIds.size > 0) {
      matchedTasks = context.tasks.filter((t) => tIds.has(t.id));
    }
  }

  return {
    sessions: matchedSessions.map((s) => ({
      id: s.id,
      gameName: s.gameName,
      platform: s.platform,
      startedAt: s.startedAt,
      score: s.score,
      performance: s.performance
    })),
    memories: matchedMemories.map((m) => ({
      id: m.id,
      title: m.title,
      memoryType: m.memoryType,
      gameName: m.gameName
    })),
    tasks: matchedTasks.map((t) => ({
      id: t.id,
      title: t.title,
      priority: t.priority,
      completed: t.completed
    }))
  };
};

/**
 * Pluggable AI Provider Adapter
 * 
 * Supports Gemini AI with automatic fallback to development adapter
 * 
 * @param {string} message - User message
 * @param {Object} context - User gaming context
 * @param {Array} [history=[]] - Bounded conversation history
 * @returns {Promise<{ message: string, insights?: Array<string>, sources: Object, provider: string }>}
 */
const generateResponse = async (message, context, history = []) => {
  const provider = (process.env.AI_PROVIDER || 'development').toLowerCase();
  const apiKey = process.env.AI_API_KEY;

  // 1. Intelligent context selection
  const intelligentContext = selectIntelligentContext(message, context);

  // 2. Development adapter mode
  if (provider === 'development' || !apiKey) {
    const reply = generateDevelopmentResponse(message, intelligentContext);
    return {
      message: reply,
      insights: [],
      sources: buildSources(intelligentContext),
      provider: 'development'
    };
  }

  // 3. Gemini mode
  if (provider === 'gemini') {
    try {
      const completion = await generateGeminiCompletion(message, intelligentContext, history);

      const sources = buildSources(intelligentContext, completion.referencedSourceIds);
      return {
        message: completion.message || 'I have analyzed your Second Brain records.',
        insights: Array.isArray(completion.insights) ? completion.insights : [],
        sources,
        provider: 'gemini'
      };
    } catch (geminiError) {
      // Clean error handling: do NOT leak secrets, database credentials, or stack traces
      const errorMessage = geminiError.message || '';

      // If configuration or API key issue, safely fall back to development mode
      if (
        errorMessage.includes('AI_API_KEY') ||
        errorMessage.includes('API key') ||
        errorMessage.includes('not configured') ||
        errorMessage.includes('API_KEY_INVALID')
      ) {
        const reply = generateDevelopmentResponse(message, intelligentContext);
        return {
          message: reply,
          insights: [],
          sources: buildSources(intelligentContext),
          provider: 'development'
        };
      }

      // If malformed AI response or other provider error
      return {
        message: 'The Copilot is temporarily unavailable. Please try again.',
        insights: [],
        sources: { sessions: [], memories: [], tasks: [] },
        provider: 'gemini'
      };
    }
  }

  // Unknown provider fallback
  const fallbackReply = generateDevelopmentResponse(message, intelligentContext);
  return {
    message: fallbackReply,
    insights: [],
    sources: buildSources(intelligentContext),
    provider: 'development'
  };
};

/**
 * Process chat interaction: retrieve context, bound history, and generate response
 * Supports existing requests without conversationId as well as multi-turn conversations
 * 
 * @param {Object} param0 
 * @param {string} param0.userId - Authenticated user UUID
 * @param {string} param0.message - User query
 * @param {string} [param0.conversationId] - Optional existing conversation UUID
 * @returns {Promise<{ message: string, insights?: Array<string>, sources: Object, provider: string, conversationId: string }>}
 */
const processChat = async ({ userId, message, conversationId = null }) => {
  let targetConversationId = conversationId;
  let history = [];

  if (targetConversationId) {
    // 1. Verify the conversation belongs to req.user.id
    await chatHistoryService.verifyConversationOwnership(targetConversationId, userId);
    // 2. Load recent messages from that conversation (bounded)
    history = await chatHistoryService.getRecentConversationMessages(targetConversationId, userId, 15);
  } else {
    // Automatically create a new conversation with deterministic title
    const title = chatHistoryService.generateConversationTitle(message);
    const convo = await chatHistoryService.createConversation({ userId, title });
    targetConversationId = convo.id;
  }

  // 3. Retrieve the existing Second Brain context
  const context = await getUserContext(userId);

  // 4 & 5. Use existing intelligent context selection and send to AI provider
  // 6. Generate the response
  const result = await generateResponse(message, context, history);

  // 7. Save user message
  await chatHistoryService.saveUserMessage({
    conversationId: targetConversationId,
    content: message
  });

  // 8. Save assistant response
  await chatHistoryService.saveAssistantMessage({
    conversationId: targetConversationId,
    content: result.message,
    provider: result.provider,
    sources: result.sources
  });

  // 9. Return the response with conversationId
  return {
    ...result,
    conversationId: targetConversationId
  };
};

module.exports = {
  getUserContext,
  selectIntelligentContext,
  generateDevelopmentResponse,
  generateGeminiCompletion,
  buildSources,
  generateResponse,
  processChat
};

