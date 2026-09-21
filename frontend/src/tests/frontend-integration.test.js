import http from 'http';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { createServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url);

// Load backend .env using native fs so database credentials and JWT_SECRET are active
const backendEnvPath = path.resolve(__dirname, '../../../backend/.env');
if (fs.existsSync(backendEnvPath)) {
  const content = fs.readFileSync(backendEnvPath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#')) {
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx !== -1) {
        const key = trimmed.slice(0, eqIdx).trim();
        const val = trimmed.slice(eqIdx + 1).trim();
        process.env[key] = val;
      }
    }
  }
}

const backendApp = require(path.resolve(__dirname, '../../../backend/src/server.js'));
const db = require(path.resolve(__dirname, '../../../backend/src/db/index.js'));

function request(url, { method = 'GET', headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const reqHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };
    const payload = body ? JSON.stringify(body) : null;
    if (payload) {
      reqHeaders['Content-Length'] = Buffer.byteLength(payload);
    }

    const req = http.request(
      {
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname + parsed.search,
        method,
        headers: reqHeaders
      },
      (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            const json = data ? JSON.parse(data) : {};
            resolve({ status: res.statusCode, body: json, raw: data });
          } catch {
            resolve({ status: res.statusCode, raw: data });
          }
        });
      }
    );

    req.on('error', reject);
    if (payload) {
      req.write(payload);
    }
    req.end();
  });
}

async function runFrontendIntegrationTests() {
  console.log('=== STARTING FRONTEND-BACKEND INTEGRATION TESTS ===\n');

  // 1. Start Backend Server on Port 5000
  const backendServer = http.createServer(backendApp);
  await new Promise((resolve) => backendServer.listen(5000, '127.0.0.1', resolve));
  console.log('✅ Real Backend server listening on http://localhost:5000');

  // 2. Start Vite Dev Server on Port 5173
  const viteServer = await createServer({
    root: path.resolve(__dirname, '../../'),
    server: { port: 5173 }
  });
  await viteServer.listen();
  console.log('✅ Vite Frontend server listening on http://localhost:5173\n');

  const results = [];
  function record(num, name, passed, details = '') {
    results.push({ num, name, passed, details });
    const mark = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${mark} [Test ${num}] ${name}`);
    if (details) console.log(`       ${details}`);
  }

  const timestamp = Date.now();
  const testUserEmail = `fe_user_${timestamp}@example.com`;
  const testUserName = `Frontend Player ${timestamp}`;
  const testUserPassword = 'TestPassword123!';
  let authToken = '';

  try {
    // ------------------------------------------------------------------------
    // Test 1: Vite Frontend serves index.html on port 5173
    // ------------------------------------------------------------------------
    const feRes = await request('http://localhost:5173/');
    const t1Passed = feRes.status === 200 && feRes.raw.includes('AI Gaming Copilot') && feRes.raw.includes('src/main.jsx');
    record(1, 'Vite Frontend serves application entry point -> 200', t1Passed, `Status: ${feRes.status}`);

    // ------------------------------------------------------------------------
    // Test 2: Frontend -> Backend Health Endpoint (/api/health)
    // ------------------------------------------------------------------------
    const healthRes = await request('http://localhost:5000/api/health');
    const t2Passed =
      healthRes.status === 200 &&
      healthRes.body.success === true &&
      healthRes.body.database === 'connected' &&
      healthRes.body.message === 'AI Gaming Copilot API is running';
    record(2, 'Backend connectivity via GET /api/health -> 200', t2Passed, JSON.stringify(healthRes.body));

    // ------------------------------------------------------------------------
    // Test 3: Real Signup Flow (POST /api/auth/signup)
    // ------------------------------------------------------------------------
    const signupRes = await request('http://localhost:5000/api/auth/signup', {
      method: 'POST',
      body: {
        name: testUserName,
        email: testUserEmail,
        password: testUserPassword
      }
    });
    const t3Passed =
      signupRes.status === 201 &&
      signupRes.body.success === true &&
      signupRes.body.user?.id &&
      signupRes.body.user?.email === testUserEmail;
    record(3, 'Real user registration (POST /api/auth/signup) -> 201', t3Passed, `User ID: ${signupRes.body?.user?.id}`);

    // ------------------------------------------------------------------------
    // Test 4: Real Login Flow (POST /api/auth/login)
    // ------------------------------------------------------------------------
    const loginRes = await request('http://localhost:5000/api/auth/login', {
      method: 'POST',
      body: {
        email: testUserEmail,
        password: testUserPassword
      }
    });
    authToken = loginRes.body?.token;
    const t4Passed =
      loginRes.status === 200 &&
      loginRes.body.success === true &&
      Boolean(authToken) &&
      loginRes.body.user?.email === testUserEmail;
    record(4, 'Real user authentication (POST /api/auth/login) -> 200', t4Passed, `Received JWT token`);

    // ------------------------------------------------------------------------
    // Test 5: Verify Stored Token on App Startup (GET /api/auth/me)
    // ------------------------------------------------------------------------
    const meRes = await request('http://localhost:5000/api/auth/me', {
      method: 'GET',
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t5Passed =
      meRes.status === 200 &&
      meRes.body.success === true &&
      meRes.body.user?.email === testUserEmail &&
      meRes.body.user?.name === testUserName;
    record(5, 'Restore session with stored JWT (GET /api/auth/me) -> 200', t5Passed, `Authenticated user: ${meRes.body?.user?.name}`);

    // ------------------------------------------------------------------------
    // Test 6: Invalid/Expired Token rejects authentication (GET /api/auth/me) -> 401
    // ------------------------------------------------------------------------
    const badTokenRes = await request('http://localhost:5000/api/auth/me', {
      method: 'GET',
      headers: { Authorization: 'Bearer invalid-garbage-token' }
    });
    const t6Passed = badTokenRes.status === 401 && badTokenRes.body.success === false;
    record(6, 'Invalid token rejected for logout triggers -> 401', t6Passed, `Status: ${badTokenRes.status}, Message: ${badTokenRes.body.message}`);

    // ------------------------------------------------------------------------
    // Test 7: Protected Route isolation (GET /api/tasks without JWT) -> 401
    // ------------------------------------------------------------------------
    const unauthRes = await request('http://localhost:5000/api/tasks');
    const t7Passed = unauthRes.status === 401;
    record(7, 'Unauthenticated access to protected resource blocked -> 401', t7Passed, `Status: ${unauthRes.status}`);

    // ------------------------------------------------------------------------
    // Test 8: Authenticated user accessing protected resource (GET /api/tasks) -> 200
    // ------------------------------------------------------------------------
    const authTasksRes = await request('http://localhost:5000/api/tasks', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t8Passed = authTasksRes.status === 200 && Array.isArray(authTasksRes.body.tasks);
    record(8, 'Authenticated access to protected resource allowed -> 200', t8Passed, `Found tasks array`);

    // ========================================================================
    // STEP 9 GAMING DASHBOARD & SESSIONS FLOW TESTS
    // ========================================================================

    // ------------------------------------------------------------------------
    // Test 9: Fetch Games list (GET /api/games) -> 200
    // ------------------------------------------------------------------------
    const gamesRes = await request('http://localhost:5000/api/games');
    const t9Passed = gamesRes.status === 200 && Array.isArray(gamesRes.body.games);
    record(9, 'Load games catalog (GET /api/games) -> 200', t9Passed, `Found ${gamesRes.body.games?.length} games`);

    // ------------------------------------------------------------------------
    // Test 10: Create game (POST /api/games) -> 201
    // ------------------------------------------------------------------------
    const newGameName = `Apex Legends ${timestamp}`;
    const createGameRes = await request('http://localhost:5000/api/games', {
      method: 'POST',
      body: { name: newGameName, platform: 'PC' }
    });
    const testGameId = createGameRes.body?.game?.id;
    const t10Passed =
      createGameRes.status === 201 &&
      createGameRes.body.success === true &&
      Boolean(testGameId) &&
      createGameRes.body.game?.name === newGameName;
    record(10, 'Create new game (POST /api/games) -> 201', t10Passed, `Game ID: ${testGameId}, Name: ${newGameName}`);

    // ------------------------------------------------------------------------
    // Test 11: Active session initially null (GET /api/sessions/active) -> 200
    // ------------------------------------------------------------------------
    const activeInitRes = await request('http://localhost:5000/api/sessions/active', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t11Passed = activeInitRes.status === 200 && activeInitRes.body.session === null;
    record(11, 'Active session initially null when idle -> 200', t11Passed, `Session: ${activeInitRes.body.session}`);

    // ------------------------------------------------------------------------
    // Test 12: Start new gaming session (POST /api/sessions) -> 201
    // ------------------------------------------------------------------------
    const startSessionRes = await request('http://localhost:5000/api/sessions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: { gameId: testGameId, notes: 'Warmup match' }
    });
    const createdSession = startSessionRes.body?.session;
    const activeSessionId = createdSession?.id;
    const t12Passed =
      startSessionRes.status === 201 &&
      startSessionRes.body.success === true &&
      Boolean(activeSessionId) &&
      createdSession.gameName === newGameName &&
      createdSession.endedAt === null &&
      Boolean(createdSession.startedAt);
    record(12, 'Start gaming session (POST /api/sessions) -> 201', t12Passed, `Session ID: ${activeSessionId}, StartedAt: ${createdSession?.startedAt}`);

    // ------------------------------------------------------------------------
    // Test 13: Fetch currently active session (GET /api/sessions/active) -> 200
    // ------------------------------------------------------------------------
    const activeLiveRes = await request('http://localhost:5000/api/sessions/active', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t13Passed =
      activeLiveRes.status === 200 &&
      activeLiveRes.body.session?.id === activeSessionId &&
      activeLiveRes.body.session?.gameName === newGameName &&
      activeLiveRes.body.session?.endedAt === null;
    record(13, 'Fetch active session while live -> 200', t13Passed, `Game: ${activeLiveRes.body?.session?.gameName}`);

    // ------------------------------------------------------------------------
    // Test 14: Prevent multiple active sessions (POST /api/sessions) -> 409
    // ------------------------------------------------------------------------
    const secondStartRes = await request('http://localhost:5000/api/sessions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: { gameId: testGameId }
    });
    const t14Passed =
      secondStartRes.status === 409 &&
      secondStartRes.body.message === 'An active gaming session already exists';
    record(14, 'Prevent multiple active sessions in backend -> 409', t14Passed, `Status: ${secondStartRes.status}, Message: ${secondStartRes.body.message}`);

    // ------------------------------------------------------------------------
    // Test 15: Update active session score, performance, notes (PATCH /api/sessions/:id) -> 200
    // ------------------------------------------------------------------------
    const updateRes = await request(`http://localhost:5000/api/sessions/${activeSessionId}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${authToken}` },
      body: {
        score: 24,
        performance: 'Excellent',
        notes: 'Clutched round 12 with Kraber'
      }
    });
    const t15Passed =
      updateRes.status === 200 &&
      updateRes.body.success === true &&
      updateRes.body.session?.score === 24 &&
      updateRes.body.session?.performance === 'Excellent';
    record(15, 'Update active session telemetry (PATCH /api/sessions/:id) -> 200', t15Passed, `Score: ${updateRes.body?.session?.score}, Performance: ${updateRes.body?.session?.performance}`);

    // Wait 1 second so elapsed duration is >= 1
    await new Promise((r) => setTimeout(r, 1100));

    // ------------------------------------------------------------------------
    // Test 16: End active gaming session (POST /api/sessions/:id/end) -> 200
    // ------------------------------------------------------------------------
    const endRes = await request(`http://localhost:5000/api/sessions/${activeSessionId}/end`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const endedSession = endRes.body?.session;
    const t16Passed =
      endRes.status === 200 &&
      endRes.body.success === true &&
      endedSession?.endedAt !== null &&
      endedSession?.duration >= 1;
    record(16, 'End active session (POST /api/sessions/:id/end) -> 200', t16Passed, `Duration: ${endedSession?.duration}s, EndedAt: ${endedSession?.endedAt}`);

    // ------------------------------------------------------------------------
    // Test 17: Ending already-ended session returns 409
    // ------------------------------------------------------------------------
    const doubleEndRes = await request(`http://localhost:5000/api/sessions/${activeSessionId}/end`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t17Passed = doubleEndRes.status === 409;
    record(17, 'Ending already-ended session returns 409 Conflict', t17Passed, `Status: ${doubleEndRes.status}`);

    // ------------------------------------------------------------------------
    // Test 18: Active session is now null (GET /api/sessions/active) -> 200
    // ------------------------------------------------------------------------
    const activeAfterEndRes = await request('http://localhost:5000/api/sessions/active', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t18Passed = activeAfterEndRes.status === 200 && activeAfterEndRes.body.session === null;
    record(18, 'Active session is null after ending -> 200', t18Passed, `Session: ${activeAfterEndRes.body.session}`);

    // ------------------------------------------------------------------------
    // Test 19: Session appears in user history (GET /api/sessions) -> 200
    // ------------------------------------------------------------------------
    const historyRes = await request('http://localhost:5000/api/sessions', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t19Passed =
      historyRes.status === 200 &&
      Array.isArray(historyRes.body.sessions) &&
      historyRes.body.sessions.some((s) => s.id === activeSessionId && s.score === 24);
    record(19, 'Ended session appears in user history (GET /api/sessions) -> 200', t19Passed, `Found in history: ${t19Passed}`);

    // ========================================================================
    // STEP 10 AI COPILOT & SECOND BRAIN FOUNDATION TESTS
    // ========================================================================

    // ------------------------------------------------------------------------
    // Test 20: AI Chat endpoint requires authentication -> 401
    // ------------------------------------------------------------------------
    const aiUnauthRes = await request('http://localhost:5000/api/ai/chat', {
      method: 'POST',
      body: { message: 'Hello' }
    });
    const t20Passed = aiUnauthRes.status === 401 && aiUnauthRes.body.success === false;
    record(20, 'AI Chat requires authentication (POST /api/ai/chat) -> 401', t20Passed, `Status: ${aiUnauthRes.status}`);

    // ------------------------------------------------------------------------
    // Test 21: AI Chat accepts authenticated question with Second Brain sources -> 200
    // ------------------------------------------------------------------------
    const aiChatRes = await request('http://localhost:5000/api/ai/chat', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: { message: 'What gaming data do you have for me?' }
    });
    const aiData = aiChatRes.body?.data;
    const t21Passed =
      aiChatRes.status === 200 &&
      aiChatRes.body.success === true &&
      typeof aiData?.message === 'string' &&
      Array.isArray(aiData?.sources?.sessions) &&
      aiData.sources.sessions.some((s) => s.id === activeSessionId);
    record(21, 'AI Chat accepts query with scoped Second Brain sources -> 200', t21Passed, `Sessions count: ${aiData?.sources?.sessions?.length}`);

    // ------------------------------------------------------------------------
    // Test 22: AI Chat answers suggested question "When did I perform best?" -> 200
    // ------------------------------------------------------------------------
    const aiBestRes = await request('http://localhost:5000/api/ai/chat', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: { message: 'When did I perform best?' }
    });
    const bestMsg = aiBestRes.body?.data?.message || '';
    const t22Passed =
      aiBestRes.status === 200 &&
      (bestMsg.includes('24') || bestMsg.includes('score') || bestMsg.includes(newGameName));
    record(22, 'AI Chat synthesizes response from Second Brain session data -> 200', t22Passed, `Message preview: "${bestMsg.slice(0, 60)}..."`);

    // ------------------------------------------------------------------------
    // Test 23: Vite serves /copilot client route entry point -> 200
    // ------------------------------------------------------------------------
    const copilotRouteRes = await request('http://localhost:5173/copilot');
    const t23Passed = copilotRouteRes.status === 200 && copilotRouteRes.raw.includes('AI Gaming Copilot');
    record(23, 'Frontend serves /copilot application route -> 200', t23Passed, `Status: ${copilotRouteRes.status}`);

    // ========================================================================
    // STEP 12 PERSISTENT AI CHAT HISTORY TESTS
    // ========================================================================

    // ------------------------------------------------------------------------
    // Test 24: Unauthenticated access to conversations blocked -> 401
    // ------------------------------------------------------------------------
    const unauthConvoRes = await request('http://localhost:5000/api/ai/conversations');
    const t24Passed = unauthConvoRes.status === 401 && unauthConvoRes.body.success === false;
    record(24, 'Unauthenticated access to conversation history blocked -> 401', t24Passed, `Status: ${unauthConvoRes.status}`);

    // ------------------------------------------------------------------------
    // Test 25: Authenticated user loads conversations -> 200
    // ------------------------------------------------------------------------
    const listConvoRes = await request('http://localhost:5000/api/ai/conversations', {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t25Passed =
      listConvoRes.status === 200 &&
      listConvoRes.body.success === true &&
      Array.isArray(listConvoRes.body.data?.conversations);
    record(25, 'Authenticated user loads conversations -> 200', t25Passed, `Found ${listConvoRes.body?.data?.conversations?.length} conversations`);

    // ------------------------------------------------------------------------
    // Test 26: Create new conversation explicitly -> 201
    // ------------------------------------------------------------------------
    const newConvoRes = await request('http://localhost:5000/api/ai/conversations', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: { title: 'Apex Clutch Breakdown' }
    });
    const feConvoId = newConvoRes.body?.data?.conversation?.id;
    const t26Passed =
      newConvoRes.status === 201 &&
      newConvoRes.body.success === true &&
      Boolean(feConvoId) &&
      newConvoRes.body?.data?.conversation?.title === 'Apex Clutch Breakdown';
    record(26, 'Create new persistent conversation -> 201', t26Passed, `Conversation ID: ${feConvoId}`);

    // ------------------------------------------------------------------------
    // Test 27: Send chat message associated with conversation -> 200
    // ------------------------------------------------------------------------
    const sendInConvoRes = await request('http://localhost:5000/api/ai/chat', {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken}` },
      body: {
        message: 'How did I perform in Apex Legends?',
        conversationId: feConvoId
      }
    });
    const t27Passed =
      sendInConvoRes.status === 200 &&
      sendInConvoRes.body.success === true &&
      sendInConvoRes.body?.data?.conversationId === feConvoId &&
      typeof sendInConvoRes.body?.data?.message === 'string';
    record(27, 'Send chat message linked to conversation -> 200', t27Passed, `Returned conversationId: ${sendInConvoRes.body?.data?.conversationId}`);

    // ------------------------------------------------------------------------
    // Test 28: Reload conversation (restores messages across refresh) -> 200
    // ------------------------------------------------------------------------
    const reloadConvoRes = await request(`http://localhost:5000/api/ai/conversations/${feConvoId}`, {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const restoredMessages = reloadConvoRes.body?.data?.conversation?.messages || [];
    const t28Passed =
      reloadConvoRes.status === 200 &&
      reloadConvoRes.body.success === true &&
      restoredMessages.length >= 2 &&
      restoredMessages.some((m) => m.role === 'user') &&
      restoredMessages.some((m) => m.role === 'assistant');
    record(28, 'Restore conversation messages across refresh -> 200', t28Passed, `Restored messages count: ${restoredMessages.length}`);

    // ------------------------------------------------------------------------
    // Test 29: Delete conversation -> 200
    // ------------------------------------------------------------------------
    const deleteConvoRes = await request(`http://localhost:5000/api/ai/conversations/${feConvoId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${authToken}` }
    });
    const t29Passed = deleteConvoRes.status === 200 && deleteConvoRes.body.success === true;
    record(29, 'Delete conversation -> 200', t29Passed, `Status: ${deleteConvoRes.status}`);


    // Clean up test user & game in PostgreSQL
    console.log('\n--- CLEANING UP TEST DATA ---');
    await db.query('DELETE FROM users WHERE email = $1;', [testUserEmail]);
    if (testGameId) {
      await db.query('DELETE FROM games WHERE id = $1;', [testGameId]);
    }
    console.log(`Cleaned up test user & game from database.`);

  } catch (error) {
    console.error('Integration test error:', error);
  } finally {
    await viteServer.close();
    await new Promise((resolve) => backendServer.close(resolve));
    await db.pool.end();
  }

  const allPassed = results.every((r) => r.passed);
  console.log(`\n=== SUMMARY: ${results.filter((r) => r.passed).length}/${results.length} INTEGRATION TESTS PASSED ===`);
  process.exit(allPassed ? 0 : 1);
}

runFrontendIntegrationTests();
