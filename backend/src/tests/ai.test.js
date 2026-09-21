const http = require('http');
const app = require('../server');
const db = require('../db');

function request(server, { method, path, headers = {}, body = null }) {
  return new Promise((resolve, reject) => {
    const address = server.address();
    const port = address.port;

    const payload = body ? JSON.stringify(body) : null;
    const reqHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };

    if (payload) {
      reqHeaders['Content-Length'] = Buffer.byteLength(payload);
    }

    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path,
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
          } catch (e) {
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

async function runAiTests() {
  console.log('=== STARTING AI COPILOT TEST SUITE ===\n');

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const testPort = server.address().port;
  console.log(`Test server running on port ${testPort}\n`);

  const timestamp = Date.now();
  const userAEmail = `ai_user_a_${timestamp}@example.com`;
  const userBEmail = `ai_user_b_${timestamp}@example.com`;
  const password = 'Password123!';

  let userAToken, userBToken;
  let userAId, userBId;
  let gameAId, gameBId;
  let sessionAId, sessionBId;
  let memoryAId, memoryBId;
  let taskAId, taskBId;

  let passedTests = 0;
  const totalTests = 13;

  try {
    // 1. Setup User A
    await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'AI Player One', email: userAEmail, password }
    });
    const loginA = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: userAEmail, password }
    });
    userAToken = loginA.body.token;
    userAId = loginA.body.user.id;

    // 2. Setup User B
    await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'AI Player Two', email: userBEmail, password }
    });
    const loginB = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: userBEmail, password }
    });
    userBToken = loginB.body.token;
    userBId = loginB.body.user.id;

    // 3. Populate User A data (Game, Session, Memory, Task)
    const gameARes = await request(server, {
      method: 'POST',
      path: '/api/games',
      headers: { Authorization: `Bearer ${userAToken}` },
      body: { name: `Valorant Pro ${timestamp}`, platform: 'PC' }
    });
    gameAId = gameARes.body.game.id;

    const sessionARes = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${userAToken}` },
      body: {
        gameId: gameAId,
        score: 98,
        performance: 'MVP Radiant',
        notes: 'Clutched round 24 on Ascent'
      }
    });
    sessionAId = sessionARes.body.session.id;

    const memoryARes = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${userAToken}` },
      body: {
        title: 'Ascent A-Site Clutch Ace',
        summary: '1v4 retake with Phantom',
        memoryType: 'highlight',
        sessionId: sessionAId,
        metadata: { weapon: 'Phantom', kills: 4 }
      }
    });
    memoryAId = memoryARes.body.memory.id;

    const taskARes = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${userAToken}` },
      body: {
        title: 'Review Ascent VoD',
        description: 'Analyze crosshair placement',
        priority: 'high',
        estimatedMinutes: 30
      }
    });
    taskAId = taskARes.body.task.id;

    // 4. Populate User B data (User B should be strictly isolated from User A)
    const gameBRes = await request(server, {
      method: 'POST',
      path: '/api/games',
      headers: { Authorization: `Bearer ${userBToken}` },
      body: { name: `Apex Legends ${timestamp}`, platform: 'PlayStation' }
    });
    gameBId = gameBRes.body.game.id;

    const sessionBRes = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${userBToken}` },
      body: {
        gameId: gameBId,
        score: 45,
        performance: 'Average',
        notes: 'User B private notes'
      }
    });
    sessionBId = sessionBRes.body.session.id;

    const memoryBRes = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${userBToken}` },
      body: {
        title: 'User B Private Memory',
        summary: 'Confidential B memory',
        memoryType: 'note',
        sessionId: sessionBId
      }
    });
    memoryBId = memoryBRes.body.memory.id;

    const taskBRes = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${userBToken}` },
      body: {
        title: 'User B Secret Task',
        priority: 'low'
      }
    });
    taskBId = taskBRes.body.task.id;

    // TEST 1: Authenticated request accepted
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: 'Hello Copilot!' }
      });
      if (res.status === 200 && res.body.success === true && res.body.data && res.body.data.message) {
        console.log('✅ PASS [Test 1] Authenticated chat request accepted -> 200');
        console.log(`       Provider: ${res.body.data.provider}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 1] Authenticated request failed:', res);
      }
    }

    // TEST 2: Unauthenticated request rejected with 401
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        body: { message: 'Hello without token' }
      });
      if (res.status === 401 && res.body.success === false) {
        console.log('✅ PASS [Test 2] Unauthenticated chat returns 401');
        console.log(`       Message: ${res.body.message}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 2] Expected 401 for unauthenticated chat:', res);
      }
    }

    // TEST 3: Invalid token returns 401
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: 'Bearer invalid.fake.token' },
        body: { message: 'Hello with fake token' }
      });
      if (res.status === 401 && res.body.success === false) {
        console.log('✅ PASS [Test 3] Invalid token rejected -> 401');
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 3] Expected 401 for invalid token:', res);
      }
    }

    // TEST 4: Empty string message rejected with 400
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: '' }
      });
      if (res.status === 400 && res.body.success === false && res.body.message.includes('required')) {
        console.log('✅ PASS [Test 4] Empty message rejected -> 400');
        console.log(`       Message: ${res.body.message}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 4] Expected 400 for empty message:', res);
      }
    }

    // TEST 5: Whitespace-only message rejected with 400
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: '     ' }
      });
      if (res.status === 400 && res.body.success === false && res.body.message.includes('required')) {
        console.log('✅ PASS [Test 5] Whitespace-only message rejected -> 400');
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 5] Expected 400 for whitespace-only message:', res);
      }
    }

    // TEST 6: Missing message property rejected with 400
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: {}
      });
      if (res.status === 400 && res.body.success === false && res.body.message.includes('required')) {
        console.log('✅ PASS [Test 6] Missing message property rejected -> 400');
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 6] Expected 400 for missing message:', res);
      }
    }

    // TEST 7: Invalid message type (number/boolean) rejected with 400
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: 12345 }
      });
      if (res.status === 400 && res.body.success === false && res.body.message.includes('string')) {
        console.log('✅ PASS [Test 7] Non-string message type rejected -> 400');
        console.log(`       Message: ${res.body.message}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 7] Expected 400 for non-string message:', res);
      }
    }

    // TEST 8: Overly long message (>2000 chars) rejected with 400
    {
      const longMessage = 'A'.repeat(2001);
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: longMessage }
      });
      if (res.status === 400 && res.body.success === false && res.body.message.includes('2000 characters')) {
        console.log('✅ PASS [Test 8] Overly long message (>2000 chars) rejected -> 400');
        console.log(`       Message: ${res.body.message}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 8] Expected 400 for message > 2000 chars:', res);
      }
    }

    // TEST 9: Context retrieval strictly isolates User A's data from User B's data
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: 'Tell me about my sessions and memories.' }
      });

      const data = res.body.data;
      const sources = data?.sources || {};

      const hasUserASession = sources.sessions?.some((s) => s.id === sessionAId);
      const hasUserBSession = sources.sessions?.some((s) => s.id === sessionBId);
      const hasUserAMemory = sources.memories?.some((m) => m.id === memoryAId);
      const hasUserBMemory = sources.memories?.some((m) => m.id === memoryBId);
      const hasUserATask = sources.tasks?.some((t) => t.id === taskAId);
      const hasUserBTask = sources.tasks?.some((t) => t.id === taskBId);

      if (
        res.status === 200 &&
        hasUserASession &&
        !hasUserBSession &&
        hasUserAMemory &&
        !hasUserBMemory &&
        hasUserATask &&
        !hasUserBTask
      ) {
        console.log('✅ PASS [Test 9] User data strictly isolated in Second Brain context (No cross-user leakage)');
        console.log(`       User A sources: ${sources.sessions.length} sessions, ${sources.memories.length} memories, ${sources.tasks.length} tasks`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 9] Cross-user leakage detected:', {
          hasUserASession,
          hasUserBSession,
          hasUserAMemory,
          hasUserBMemory,
          hasUserATask,
          hasUserBTask
        });
      }
    }

    // TEST 10: Client-provided spoofed userId is ignored; authenticated user is used
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: {
          message: 'What are my tasks?',
          userId: userBId // Attempt to spoof User B's id
        }
      });

      const sources = res.body.data?.sources || {};
      const containsUserBTask = sources.tasks?.some((t) => t.id === taskBId);
      const containsUserATask = sources.tasks?.some((t) => t.id === taskAId);

      if (res.status === 200 && !containsUserBTask && containsUserATask) {
        console.log('✅ PASS [Test 10] Client-provided userId spoofing ignored; req.user.id strictly enforced');
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 10] User ID spoofing was not properly ignored:', res.body);
      }
    }

    // TEST 11: Response structure conforms to expected schema
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: 'How is my gaming?' }
      });

      const hasValidStructure =
        res.status === 200 &&
        res.body.success === true &&
        typeof res.body.data === 'object' &&
        typeof res.body.data.message === 'string' &&
        typeof res.body.data.sources === 'object' &&
        Array.isArray(res.body.data.sources.sessions) &&
        Array.isArray(res.body.data.sources.memories) &&
        Array.isArray(res.body.data.sources.tasks) &&
        typeof res.body.data.provider === 'string';

      if (hasValidStructure) {
        console.log('✅ PASS [Test 11] API response adheres strictly to schema');
        console.log(`       Provider: ${res.body.data.provider}`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 11] Invalid response structure:', res.body);
      }
    }

    // TEST 12: Context-aware development query answers from real data
    {
      const res = await request(server, {
        method: 'POST',
        path: '/api/ai/chat',
        headers: { Authorization: `Bearer ${userAToken}` },
        body: { message: 'When did I perform best?' }
      });

      const reply = res.body.data?.message || '';
      // Score was 98 for Valorant Pro
      if (res.status === 200 && (reply.includes('98') || reply.includes('strongest') || reply.includes('Valorant'))) {
        console.log('✅ PASS [Test 12] Development query synthesis accurately reflects real Second Brain session');
        console.log(`       Response snippet: "${reply.slice(0, 80)}..."`);
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 12] Expected context synthesis in response:', reply);
      }
    }

    // TEST 13: Health endpoint still works
    {
      const res = await request(server, {
        method: 'GET',
        path: '/api/health'
      });
      if (res.status === 200 && res.body.success === true && res.body.database === 'connected') {
        console.log('✅ PASS [Test 13] Health endpoint returns 200 with database connected');
        passedTests++;
      } else {
        console.error('❌ FAIL [Test 13] Health endpoint check failed:', res);
      }
    }
  } catch (err) {
    console.error('Unexpected test error:', err);
  } finally {
    // Teardown test data
    console.log('\n--- CLEANUP TEST DATA ---');
    try {
      if (taskAId || taskBId) {
        await db.query('DELETE FROM tasks WHERE user_id IN ($1, $2)', [userAId, userBId]);
      }
      if (memoryAId || memoryBId) {
        await db.query('DELETE FROM gaming_memories WHERE user_id IN ($1, $2)', [userAId, userBId]);
      }
      if (sessionAId || sessionBId) {
        await db.query('DELETE FROM gaming_sessions WHERE user_id IN ($1, $2)', [userAId, userBId]);
      }
      if (gameAId || gameBId) {
        await db.query('DELETE FROM games WHERE id IN ($1, $2)', [gameAId, gameBId]);
      }
      if (userAId || userBId) {
        await db.query('DELETE FROM users WHERE id IN ($1, $2)', [userAId, userBId]);
      }
      console.log('Test users, games, sessions, memories, and tasks cleaned up.');
    } catch (cleanupErr) {
      console.error('Error during cleanup:', cleanupErr);
    }

    await new Promise((resolve) => server.close(resolve));
    console.log(`\n=== SUMMARY: ${passedTests}/${totalTests} AI TESTS PASSED ===\n`);
    if (passedTests !== totalTests) {
      process.exit(1);
    }
  }
}

runAiTests();
