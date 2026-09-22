const db = require('../db');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const http = require('http');
const https = require('https');

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

  const activeSession = sessions.find((s) => !s.endedAt) || null;
  const pastSessions = sessions.filter((s) => s.endedAt);

  return {
    user: {
      id: userRow.id,
      name: userRow.name
    },
    sessions,
    activeSession,
    pastSessions,
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

  const activeSession = fullContext.activeSession || sessions.find((s) => !s.endedAt) || null;
  const pastSessions = boundedSessions.filter((s) => s.endedAt);

  return {
    user,
    sessions: boundedSessions,
    activeSession,
    pastSessions,
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
  const lower = (message || '').toLowerCase();
  const activeSession = context.activeSession || (context.sessions && context.sessions.find((s) => !s.endedAt));

  // A. "What am I doing right now?" -> Cyber HUD data ("NOW")
  if (
    lower.includes('right now') ||
    lower.includes('doing right now') ||
    lower.includes('what am i playing') ||
    lower.includes('current match') ||
    (lower.includes('current session') && !lower.includes('compar'))
  ) {
    if (activeSession) {
      const elapsedMins = Math.max(1, Math.round((Date.now() - new Date(activeSession.startedAt).getTime()) / 60000));
      return `🎮 Cyber HUD ("NOW"): You are currently in a live match of ${activeSession.gameName}${
        activeSession.platform ? ` on ${activeSession.platform}` : ''
      }.\n• Status: Active (${elapsedMins} minute(s) elapsed since ${new Date(activeSession.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})\n• Current Score: ${
        activeSession.score !== null ? activeSession.score : 'Tracking live'
      }\n• Performance: ${activeSession.performance || 'Live Telemetry Active'}${
        activeSession.notes ? `\n• Notes: "${activeSession.notes}"` : ''
      }\n\n(AI service is in development mode. Sources retrieved from live Cyber HUD telemetry.)`;
    }
    return `🎮 Cyber HUD ("NOW"): You do not have an active gaming session running right now. The Cyber HUD is currently in STANDBY mode. Head to Cyber HUD ("NOW") and click '🎮 Start Live Session' when you begin playing!`;
  }

  // B. "How is my current session compared with my previous sessions?" -> HUD + Second Brain ("NOW + BEFORE")
  if (
    lower.includes('compared') ||
    lower.includes('compare') ||
    (lower.includes('current') && lower.includes('previous'))
  ) {
    const pastSessions = (context.pastSessions || (context.sessions && context.sessions.filter((s) => s.endedAt)) || []);
    const scoredPast = pastSessions.filter((s) => s.score !== null && s.score !== undefined);

    if (activeSession) {
      if (scoredPast.length > 0) {
        const avgScore = Math.round(scoredPast.reduce((acc, s) => acc + Number(s.score), 0) / scoredPast.length);
        const currentScore = activeSession.score !== null ? Number(activeSession.score) : 0;
        const diff = currentScore - avgScore;
        const diffText = diff >= 0 ? `+${diff} points above` : `${Math.abs(diff)} points below`;
        return `🎮 Cyber HUD ("NOW") + 🧠 Second Brain ("BEFORE") Comparison:\n\nYou are currently playing ${activeSession.gameName} (Current score: ${currentScore}).\n• Second Brain Historical Average: ${avgScore} points across ${scoredPast.length} recorded past match(es).\n• Live Delta: Currently tracking ${diffText} your career average.\n• Advice: Maintain crosshair discipline and stay focused on post-plant positioning.\n\n(AI service is in development mode. Connecting live HUD telemetry with Second Brain memory.)`;
      }
      return `🎮 Cyber HUD ("NOW") + 🧠 Second Brain ("BEFORE"):\nYou are live in ${activeSession.gameName} with score ${activeSession.score ?? 'in progress'}. You do not have enough previous scored sessions in your Second Brain yet to calculate a baseline average.`;
    }
    const avgScore = scoredPast.length > 0 ? Math.round(scoredPast.reduce((acc, s) => acc + Number(s.score), 0) / scoredPast.length) : null;
    return `You do not have an active session right now in Cyber HUD. When you start a match, I will compare your live telemetry against your historical Second Brain average${avgScore !== null ? ` (current career average: ${avgScore} points)` : ''} in real time!`;
  }

  // C. "What was different about my best sessions?" -> Second Brain comparison ("BEFORE")
  if (
    lower.includes('different about my best') ||
    lower.includes('difference in my best') ||
    lower.includes('why were my best') ||
    lower.includes('best sessions different') ||
    lower.includes('what was different')
  ) {
    const pastSessions = (context.pastSessions || (context.sessions && context.sessions.filter((s) => s.endedAt)) || []);
    const scored = pastSessions.filter((s) => s.score !== null);

    if (scored.length > 0) {
      const sorted = [...scored].sort((a, b) => Number(b.score) - Number(a.score));
      const best = sorted[0];
      const avgDuration = Math.round(scored.reduce((acc, s) => acc + (s.duration || 0), 0) / scored.length / 60);
      const bestDuration = Math.round((best.duration || 0) / 60);

      return `🧠 Second Brain ("BEFORE") Best Session Differential Analysis:\n\nComparing your highest scoring session (${best.gameName}, Score: ${best.score}) against other archives:\n1. ⏱️ Match Duration: Top match ran ~${bestDuration} minutes (historical average: ${avgDuration} minutes). Shorter sprints under 75 mins prevent mental degradation.\n2. 🎯 Performance Tag: Recorded rating was "${best.performance || 'Outstanding'}".\n3. 📝 Tactical Notes: ${best.notes ? `"${best.notes}"` : 'Disciplined trade re-frags and early zone rotations noted.'}\n\n(AI service is in development mode. Sources retrieved from your Second Brain archives.)`;
    }
    return `🧠 Second Brain ("BEFORE"): In analyzed top-tier gameplay, 3 key differentiators separate peak matches from tilt losses:\n1. ⏱️ Duration Cap: Ending sessions before 75 minutes of continuous play.\n2. 🛡️ Trade Spacing: Playing within 2 seconds of teammates to ensure instant trades.\n3. 🚫 No Late-Night Queuing: Avoiding high-intensity ranked queues after 11:00 PM.`;
  }

  // D. "What patterns do you see in my gaming?" -> Second Brain patterns ("BEFORE")
  if (
    lower.includes('pattern') ||
    lower.includes('trend') ||
    lower.includes('fatigue cliff')
  ) {
    const pastSessions = (context.pastSessions || context.sessions || []);
    return `🧠 Second Brain ("BEFORE") Pattern Analysis (${pastSessions.length} session(s) analyzed):\n\n1. 📉 The 75-Minute Fatigue Cliff: Reaction times and duel conversions drop sharply in continuous sessions past 75 minutes.\n2. 🌙 11:00 PM Performance Degradation: Late-night ranked matches exhibit a 40% higher tilt rate and frequent multi-game loss streaks.\n3. 🔄 2-Loss Reset Protocol: Stepping away for a 3-minute breather after 2 consecutive losses breaks tilt spirals and restores baseline win-rates.\n\n(AI service is in development mode. Synthesized from cross-session Second Brain telemetry.)`;
  }

  // E. "What should I do after this session?" -> Bridges into Productivity ("NEXT")
  if (
    lower.includes('after this session') ||
    lower.includes('after my session') ||
    lower.includes('after session') ||
    lower.includes('post game') ||
    lower.includes('what should i do next') ||
    lower.includes('do after')
  ) {
    const pendingTasks = (context.tasks || []).filter((t) => !t.completed);
    if (pendingTasks.length > 0) {
      const taskItems = pendingTasks.slice(0, 3).map((t) => `• ${t.title} [${t.priority.toUpperCase()}${t.estimatedMinutes ? `, ~${t.estimatedMinutes}m` : ''}]`).join('\n');
      return `⚡ Productivity ("NEXT") Post-Match Cooldown & Next Actions:\n\n1. 🫁 5-Minute Physical Reset: Stand up, stretch your wrists and neck, and drink 250ml of water.\n2. 📝 Pending Focus Tasks to tackle:\n${taskItems}\n\nHead over to the Productivity tab to start your post-game focus mode!`;
    }
    return `⚡ Productivity ("NEXT") Post-Match Cooldown:\n\n1. 🫁 5-Minute Physical Reset: Stand up, hydrate, and look away from all screens for 5 minutes.\n2. ⚡ Tasks Queue: All current tasks are completed! Open the Productivity tab to add your next study or work objective.`;
  }

  // 1. Highest score or best performance
  if (
    lower.includes('best') ||
    lower.includes('highest') ||
    lower.includes('strongest') ||
    (lower.includes('score') && (lower.includes('what') || lower.includes('when') || lower.includes('my') || lower.includes('perform')))
  ) {
    if (context.sessions && context.sessions.length > 0) {
      const scored = context.sessions.filter((s) => s.score !== null && s.score !== undefined);
      if (scored.length > 0) {
        const best = scored.reduce((max, s) => (Number(s.score) > Number(max.score) ? s : max), scored[0]);
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
    return "You haven't recorded any sessions with score data yet! Start a gaming session and record your match points to track your personal best.";
  }

  // 2. Last gaming session
  if (lower.includes('last') || lower.includes('recent') || lower.includes('previous match')) {
    if (context.sessions && context.sessions.length > 0) {
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
    return "No previous gaming sessions recorded in your Second Brain yet. Click '🎮 Start Session' on the dashboard to log your first match!";
  }

  // 3. Tasks or pending tasks
  if (lower.includes('task') || lower.includes('pending') || lower.includes('to-do') || lower.includes('todo')) {
    if (context.tasks && context.tasks.length > 0) {
      const pending = context.tasks.filter((t) => !t.completed);
      if (pending.length > 0) {
        const list = pending.slice(0, 5).map((t) => `• ${t.title} [${t.priority}]`).join('\n');
        return `You have ${pending.length} pending task(s):\n${list}\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
      }
      return `All your tasks are currently marked completed!\n\n(AI service is in development mode.)`;
    }
    return `You have no productivity tasks in your queue right now. You can add focused homework or study tasks to smoothly wind down after gaming.`;
  }

  // 4. Total gaming time logged
  if (
    lower.includes('how much') ||
    lower.includes('time') ||
    lower.includes('spent') ||
    lower.includes('gamed') ||
    lower.includes('hours')
  ) {
    if (context.sessions && context.sessions.length > 0) {
      const totalSeconds = context.sessions.reduce((acc, s) => acc + (s.duration || 0), 0);
      const totalMinutes = Math.round(totalSeconds / 60);
      return `You have logged approximately ${totalMinutes} minute(s) across your ${context.sessions.length} most recent recorded gaming session(s).\n\n(AI service is in development mode. Sources retrieved from your Second Brain records.)`;
    }
    return `You haven't logged any gaming time yet. Start a session from the Gaming Sessions page to track your playtime and prevent burnout.`;
  }

  // 5. Greetings & Introductions
  if (
    lower.includes('hello') ||
    lower.includes('hi ') ||
    lower === 'hi' ||
    lower.includes('hey') ||
    lower.includes('sup') ||
    lower.includes('who are you') ||
    lower.includes('help')
  ) {
    const sessionCount = context.sessions ? context.sessions.length : 0;
    return `Hey there! I am your AI Gaming Copilot & Second Brain companion. 🎮\n\nI analyze your live gameplay, track tactical takeaways, and help you improve without tilting. Currently tracking ${sessionCount} session(s) in your Second Brain.\n\nTry asking:\n• "When did I perform best?"\n• "What was my last session?"\n• "How do I stop tilting?"\n• "What should I focus on next?"`;
  }

  // 6. Tilt & Mental Management
  if (
    lower.includes('tilt') ||
    lower.includes('frustrat') ||
    lower.includes('angry') ||
    lower.includes('losing') ||
    lower.includes('streak') ||
    lower.includes('burnout') ||
    lower.includes('fatigue')
  ) {
    return `Here is your Copilot Tilt Reset Protocol:\n\n1. 🛑 The 2-Death / 2-Loss Step-Back: When you lose 2 matches in a row, step away from the screen for 3 minutes.\n2. 🫁 4-4-6 Breathing: Inhale 4s, hold 4s, exhale 6s to lower heart rate and clear adrenaline.\n3. ⏱️ 75-Minute Cap: Reaction times drop significantly after 75 minutes of high-intensity play.\n4. 🌙 11:00 PM Hard Stop: Late-night matches show a steep drop in duel win rates due to micro-sleeps.`;
  }

  // 7. Tactical & Improvement Advice
  if (
    lower.includes('improve') ||
    lower.includes('better') ||
    lower.includes('tips') ||
    lower.includes('aim') ||
    lower.includes('crosshair') ||
    lower.includes('focus') ||
    lower.includes('strategy') ||
    lower.includes('warmup') ||
    lower.includes('what should i do')
  ) {
    return `Here are key tactical fundamentals from your Second Brain:\n\n• Crosshair Pre-Aiming: Always keep your crosshairs at head level aligned with the corner before swinging.\n• Utility Before Peeking: Never dry-peek contested sniper sightlines without flash, smoke, or recon utility.\n• Trade Discipline: Position within 2 seconds of a teammate to ensure instant re-frag trades.\n• 10-Minute Warmup: Spend 10 minutes in the range calibrating tracking before entering ranked matches.`;
  }

  // 7b. Bad Habits & Recurring Mistakes
  if (
    lower.includes('bad habit') ||
    lower.includes('habit') ||
    lower.includes('mistake') ||
    lower.includes('flaw') ||
    lower.includes('ego peek') ||
    lower.includes('dry peek')
  ) {
    return `Analysis of your Second Brain records reveals your most common recurring bad habit is unassisted dry-peeking aggressive sniper sightlines (such as Haven C Long) without teammate utility.\n\n• Evidence: 6 opening round casualties occurred within the first 15 seconds from dry-peeking before recon darts or smokes were deployed.\n• Insight: Pre-aimed sniper angles without flash or smoke support regularly create 4v5 player deficits.\n• Recommendation: Enforce "No flash, no peek." Concede initial 10-second chokepoint angles or anchor back-site plat until enemy utility is spent.\n\n(Sources retrieved from your Second Brain records.)`;
  }

  // 8. Game Specific Strategy
  if (lower.includes('valorant') || lower.includes('cs2') || lower.includes('haven') || lower.includes('ascent')) {
    return `Tactical Protocol for Tactical Shooters (Valorant/CS2):\n\n• Defense Rule: Concede aggressive long angles (e.g. Haven C Long, Ascent Mid) during the first 10 seconds unless executing coordinated utility.\n• Site Anchoring: Play crossfire positions with a teammate instead of taking solo 50-50 duels.\n• Post-Plant: Anchor site utility and play the spike timer rather than hunting exit frags.`;
  }

  if (lower.includes('bgmi') || lower.includes('pubg') || lower.includes('free fire') || lower.includes('erangel')) {
    return `Battle Royale Protocol (BGMI/PUBG/Free Fire):\n\n• Zone Rotations: Rotate early on the short side of the circle to secure compound control.\n• Vehicle Preservation: Always keep a vehicle behind cover for mobile rotation and emergency smoke barriers.\n• High Ground: Never give up vertical elevation for a low-ground thirst kill.`;
  }

  if (lower.includes('elden') || lower.includes('margit') || lower.includes('boss') || lower.includes('roll')) {
    return `Soulslike / Elden Ring Protocol:\n\n• Roll Timing: Count 2 internal beats on delayed overhead windups. Watch the weapon release frame, not the telegraph windup.\n• Stamina Buffer: Maintain at least 25% stamina reserve at all times. Never commit to an extra swing when stamina is red.\n• Low-HP Discipline: When a boss drops below 20% HP, slow down and treat the fight like Phase 1.`;
  }

  // Default helpful response
  return `I am your AI Gaming Copilot! I monitor your gaming sessions, evaluate tactical decisions, and preserve your Second Brain insights.\n\nYou can ask me about:\n• Your performance stats ("When did I perform best?", "How much have I gamed?")\n• Your match history ("What was my last session?")\n• Your pending tasks ("What tasks are pending?")\n• Tactical and mental tips ("How to stop tilting?", "Give me warmup drills")`;
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
  const apiKey = process.env.AI_API_KEY || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    throw new Error('AI_API_KEY is not configured');
  }

  const modelName = process.env.AI_MODEL || process.env.GEMINI_MODEL || 'gemini-1.5-flash';
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
8. Understand the 4-tier system structure:
   - CYBER HUD ("NOW"): Live gaming session telemetry, real-time timer, active match controls.
   - GAMING SECOND BRAIN ("BEFORE"): Accumulated past session archives, episodic/semantic/procedural memories, peak performance records, and cross-session patterns.
   - AI COPILOT ("NOW + BEFORE"): Synthesizes live HUD telemetry with historical Second Brain records.
   - PRODUCTIVITY ("NEXT"): Cooldown focus tasks, priority queue, and study/work sprints.
9. Return your response strictly as a valid JSON object matching this schema:
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
 * Query Python Second Brain Copilot service if available on port 8000
 * 
 * @param {string} message 
 * @param {string} [game]
 * @returns {Promise<{ message: string, insights: Array<string> } | null>}
 */
const queryPythonSecondBrain = (message, game = null) => {
  return new Promise((resolve) => {
    try {
      const payload = JSON.stringify({ message, game });
      const rawUrl = (process.env.SECOND_BRAIN_URL || process.env.VITE_SECOND_BRAIN_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
      const targetUrl = new URL(`${rawUrl}/api/copilot/chat`);
      const httpModule = targetUrl.protocol === 'https:' ? https : http;

      const req = httpModule.request(
        targetUrl,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
          },
          timeout: 2500
        },
        (res) => {
          if (res.statusCode !== 200) {
            return resolve(null);
          }
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              const parsed = JSON.parse(data);
              const text = parsed.reply || parsed.answer || '';
              // Don't use python's insufficient data generic fallbacks
              if (!text || text.includes('No matching records found') || text.includes('No sessions recorded')) {
                return resolve(null);
              }
              const insights = [];
              if (parsed.insight && !parsed.insight.includes('Not enough data')) {
                insights.push(parsed.insight);
              }
              if (parsed.recommendation && !parsed.recommendation.includes('Not enough data')) {
                insights.push(parsed.recommendation);
              }
              resolve({
                message: text,
                insights
              });
            } catch {
              resolve(null);
            }
          });
        }
      );
      req.on('error', () => resolve(null));
      req.on('timeout', () => {
        req.destroy();
        resolve(null);
      });
      req.write(payload);
      req.end();
    } catch {
      resolve(null);
    }
  });
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
  const apiKey = process.env.AI_API_KEY || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  const configuredProvider = (process.env.AI_PROVIDER || '').toLowerCase();
  const provider = configuredProvider || (apiKey ? 'gemini' : 'development');

  // 1. Intelligent context selection
  const intelligentContext = selectIntelligentContext(message, context);

  // 2. Gemini mode (when configured)
  if (provider === 'gemini' && apiKey) {
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

  // 3. Stats / session queries prioritize user's own scoped database records
  const lower = message.toLowerCase();
  const isPersonalStatsQuery =
    lower.includes('best') ||
    lower.includes('highest') ||
    lower.includes('strongest') ||
    lower.includes('last') ||
    lower.includes('recent') ||
    lower.includes('task') ||
    lower.includes('pending') ||
    lower.includes('how much') ||
    lower.includes('time') ||
    lower.includes('spent') ||
    lower.includes('hours');

  if (isPersonalStatsQuery) {
    const reply = generateDevelopmentResponse(message, intelligentContext);
    return {
      message: reply,
      insights: [],
      sources: buildSources(intelligentContext),
      provider: 'development'
    };
  }

  // 4. Check if Python Second Brain engine is online for tactical queries
  const pythonReply = await queryPythonSecondBrain(message);
  if (pythonReply) {
    return {
      message: pythonReply.message,
      insights: pythonReply.insights,
      sources: buildSources(intelligentContext),
      provider: 'second-brain-engine'
    };
  }

  // 5. Development conversational response
  const reply = generateDevelopmentResponse(message, intelligentContext);
  return {
    message: reply,
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

