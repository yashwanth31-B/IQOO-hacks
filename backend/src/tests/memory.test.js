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

async function runMemoryTests() {
  console.log('=== STARTING GAMING MEMORY TEST SUITE ===\n');

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const testPort = server.address().port;
  console.log(`Test server running on port ${testPort}\n`);

  const timestamp = Date.now();
  const userAEmail = `mem_user_a_${timestamp}@example.com`;
  const userBEmail = `mem_user_b_${timestamp}@example.com`;
  const password = 'Password123!';

  let tokenA = '';
  let tokenB = '';
  let userAId = '';
  let userBId = '';
  let testGameId = '';
  let sessionAId = '';
  let sessionBId = '';
  let memoryAId = '';
  let memoryAttachedId = '';
  let memoryBId = '';

  const results = [];

  function record(testNum, name, passed, details = '') {
    results.push({ testNum, name, passed, details });
    const mark = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${mark} [Test ${testNum}] ${name}`);
    if (details) console.log(`       ${details}`);
  }

  try {
    // ------------------------------------------------------------------------
    // SETUP: Users, Games, and Sessions
    // ------------------------------------------------------------------------
    // User A
    const regA = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Player Alpha', email: userAEmail, password }
    });
    userAId = regA.body?.user?.id;

    const loginA = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: userAEmail, password }
    });
    tokenA = loginA.body?.token;

    // User B
    const regB = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Player Beta', email: userBEmail, password }
    });
    userBId = regB.body?.user?.id;

    const loginB = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: userBEmail, password }
    });
    tokenB = loginB.body?.token;

    // Game
    const gameRes = await request(server, {
      method: 'POST',
      path: '/api/games',
      body: { name: `Valorant Mem ${timestamp}`, platform: 'PC' }
    });
    testGameId = gameRes.body?.game?.id;

    // Session for User A
    const sARes = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { gameId: testGameId, score: 1000, performance: 'Solid', notes: 'First session' }
    });
    sessionAId = sARes.body?.session?.id;

    // Session for User B
    const sBRes = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenB}` },
      body: { gameId: testGameId, score: 800, performance: 'Okay' }
    });
    sessionBId = sBRes.body?.session?.id;

    // ------------------------------------------------------------------------
    // 1. Create memory successfully
    // ------------------------------------------------------------------------
    const res1 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Best Valorant session',
        summary: 'My strongest performance after a 20 minute warm-up.',
        memoryType: 'performance'
      }
    });
    memoryAId = res1.body?.memory?.id;
    const t1Passed = res1.status === 201 && 
      res1.body.success === true && 
      res1.body.memory?.title === 'Best Valorant session' &&
      res1.body.memory?.sessionId === null;
    record(1, 'Create memory successfully -> 201', t1Passed, `Memory ID: ${memoryAId}`);

    // ------------------------------------------------------------------------
    // 2. Create memory without JWT -> 401
    // ------------------------------------------------------------------------
    const res2 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      body: {
        title: 'No token memory',
        memoryType: 'performance'
      }
    });
    const t2Passed = res2.status === 401 && res2.body.success === false;
    record(2, 'Create memory without JWT -> 401', t2Passed, `Status: ${res2.status}, Message: ${res2.body?.message}`);

    // ------------------------------------------------------------------------
    // 3. Missing title -> 400
    // ------------------------------------------------------------------------
    const res3 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { memoryType: 'performance' }
    });
    const t3Passed = res3.status === 400 && res3.body.success === false;
    record(3, 'Missing title -> 400', t3Passed, `Status: ${res3.status}, Message: ${res3.body?.message}`);

    // ------------------------------------------------------------------------
    // 4. Missing memoryType -> 400
    // ------------------------------------------------------------------------
    const res4 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Some Title' }
    });
    const t4Passed = res4.status === 400 && res4.body.success === false;
    record(4, 'Missing memoryType -> 400', t4Passed, `Status: ${res4.status}, Message: ${res4.body?.message}`);

    // ------------------------------------------------------------------------
    // 5. Invalid session UUID -> 400
    // ------------------------------------------------------------------------
    const res5 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Invalid session ref',
        memoryType: 'tactics',
        sessionId: 'not-a-valid-uuid'
      }
    });
    const t5Passed = res5.status === 400 && res5.body.success === false;
    record(5, 'Invalid session UUID -> 400', t5Passed, `Status: ${res5.status}, Message: ${res5.body?.message}`);

    // ------------------------------------------------------------------------
    // 6. Nonexistent session -> 404
    // ------------------------------------------------------------------------
    const res6 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Nonexistent session ref',
        memoryType: 'tactics',
        sessionId: '00000000-0000-0000-0000-000000000000'
      }
    });
    const t6Passed = res6.status === 404 && res6.body.success === false;
    record(6, 'Nonexistent session -> 404', t6Passed, `Status: ${res6.status}, Message: ${res6.body?.message}`);

    // ------------------------------------------------------------------------
    // 7. Attach memory to own session -> 201
    // ------------------------------------------------------------------------
    const res7 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Clutched on Haven',
        summary: 'Won 1v3 on A site',
        memoryType: 'highlight',
        sessionId: sessionAId,
        metadata: { map: 'Haven', kills: 28, deaths: 14 }
      }
    });
    memoryAttachedId = res7.body?.memory?.id;
    const t7Passed = res7.status === 201 && 
      res7.body.success === true && 
      res7.body.memory?.sessionId === sessionAId &&
      res7.body.memory?.session?.id === sessionAId &&
      res7.body.memory?.metadata?.map === 'Haven';
    record(7, 'Attach memory to own session -> 201', t7Passed, `Memory ID: ${memoryAttachedId}`);

    // ------------------------------------------------------------------------
    // 8. Prevent attaching memory to another user's session -> 404
    // ------------------------------------------------------------------------
    const res8 = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` }, // User A trying to attach to User B's session
      body: {
        title: 'Illegitimate attachment',
        memoryType: 'tactics',
        sessionId: sessionBId
      }
    });
    const t8Passed = res8.status === 404 && res8.body.success === false;
    record(8, "Prevent attaching memory to another user's session -> 404", t8Passed, `Status: ${res8.status}, Message: ${res8.body?.message}`);

    // ------------------------------------------------------------------------
    // 9. Get memories -> 200
    // ------------------------------------------------------------------------
    const res9 = await request(server, {
      method: 'GET',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t9Passed = res9.status === 200 && 
      Array.isArray(res9.body?.memories) && 
      res9.body.memories.length >= 2;
    record(9, 'Get memories -> 200', t9Passed, `Found: ${res9.body?.memories?.length} memories`);

    // ------------------------------------------------------------------------
    // 10. Pagination works -> 200
    // ------------------------------------------------------------------------
    const res10 = await request(server, {
      method: 'GET',
      path: '/api/memories?page=1&limit=1',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const pag = res10.body?.pagination;
    const t10Passed = res10.status === 200 && 
      pag?.page === 1 && 
      pag?.limit === 1 && 
      pag?.total >= 2 && 
      res10.body?.memories?.length === 1;
    record(10, 'Pagination works -> 200', t10Passed, `Page: ${pag?.page}, Limit: ${pag?.limit}, Total: ${pag?.total}`);

    // ------------------------------------------------------------------------
    // 11. memoryType filtering works
    // ------------------------------------------------------------------------
    const res11 = await request(server, {
      method: 'GET',
      path: '/api/memories?memoryType=highlight',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t11Passed = res11.status === 200 && 
      res11.body.memories.length > 0 && 
      res11.body.memories.every(m => m.memoryType === 'highlight');
    record(11, 'memoryType filtering works -> 200', t11Passed, `Filtered count: ${res11.body?.memories?.length}`);

    // ------------------------------------------------------------------------
    // 12. sessionId filtering works
    // ------------------------------------------------------------------------
    const res12 = await request(server, {
      method: 'GET',
      path: `/api/memories?sessionId=${sessionAId}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t12Passed = res12.status === 200 && 
      res12.body.memories.length > 0 && 
      res12.body.memories.every(m => m.sessionId === sessionAId);
    record(12, 'sessionId filtering works -> 200', t12Passed, `Filtered count: ${res12.body?.memories?.length}`);

    // ------------------------------------------------------------------------
    // 13. Get single memory -> 200
    // ------------------------------------------------------------------------
    const res13 = await request(server, {
      method: 'GET',
      path: `/api/memories/${memoryAttachedId}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t13Passed = res13.status === 200 && 
      res13.body.memory?.id === memoryAttachedId && 
      res13.body.memory?.session?.id === sessionAId;
    record(13, 'Get single memory -> 200', t13Passed, `Title: ${res13.body?.memory?.title}, Session Game: ${res13.body?.memory?.session?.gameName}`);

    // ------------------------------------------------------------------------
    // 14. Invalid memory UUID -> 400
    // ------------------------------------------------------------------------
    const res14 = await request(server, {
      method: 'GET',
      path: '/api/memories/not-a-valid-uuid',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t14Passed = res14.status === 400 && res14.body.success === false;
    record(14, 'Invalid memory UUID -> 400', t14Passed, `Status: ${res14.status}, Message: ${res14.body?.message}`);

    // ------------------------------------------------------------------------
    // Setup User B memory for cross-user tests
    // ------------------------------------------------------------------------
    const bMemRes = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenB}` },
      body: { title: "User B Secret Memory", memoryType: "tactics" }
    });
    memoryBId = bMemRes.body?.memory?.id;

    // ------------------------------------------------------------------------
    // 15. Access another user's memory -> 404
    // ------------------------------------------------------------------------
    const res15 = await request(server, {
      method: 'GET',
      path: `/api/memories/${memoryBId}`,
      headers: { Authorization: `Bearer ${tokenA}` } // User A accessing User B memory
    });
    const t15Passed = res15.status === 404 && res15.body.success === false;
    record(15, "Access another user's memory -> 404", t15Passed, `Status: ${res15.status}, Message: ${res15.body?.message}`);

    // ------------------------------------------------------------------------
    // 16. Update own memory -> 200
    // ------------------------------------------------------------------------
    const res16 = await request(server, {
      method: 'PATCH',
      path: `/api/memories/${memoryAttachedId}`,
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Updated Clutched on Haven',
        metadata: { map: 'Haven', kills: 30, deaths: 14, ace: true }
      }
    });
    const t16Passed = res16.status === 200 && 
      res16.body.memory?.title === 'Updated Clutched on Haven' &&
      res16.body.memory?.metadata?.ace === true;
    record(16, 'Update own memory -> 200', t16Passed, `Updated title: ${res16.body?.memory?.title}`);

    // ------------------------------------------------------------------------
    // 17. Update another user's memory -> 404
    // ------------------------------------------------------------------------
    const res17 = await request(server, {
      method: 'PATCH',
      path: `/api/memories/${memoryBId}`,
      headers: { Authorization: `Bearer ${tokenA}` }, // User A updating User B memory
      body: { title: 'Hacked title' }
    });
    const t17Passed = res17.status === 404 && res17.body.success === false;
    record(17, "Update another user's memory -> 404", t17Passed, `Status: ${res17.status}, Message: ${res17.body?.message}`);

    // ------------------------------------------------------------------------
    // 18. Delete own memory -> 200
    // ------------------------------------------------------------------------
    const tempMem = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Temporary Memory', memoryType: 'note' }
    });
    const tempMemId = tempMem.body?.memory?.id;

    const res18 = await request(server, {
      method: 'DELETE',
      path: `/api/memories/${tempMemId}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t18Passed = res18.status === 200 && res18.body.success === true;
    record(18, 'Delete own memory -> 200', t18Passed, `Deleted memory ID: ${tempMemId}`);

    // ------------------------------------------------------------------------
    // 19. Delete another user's memory -> 404
    // ------------------------------------------------------------------------
    const res19 = await request(server, {
      method: 'DELETE',
      path: `/api/memories/${memoryBId}`,
      headers: { Authorization: `Bearer ${tokenA}` } // User A deleting User B memory
    });
    const t19Passed = res19.status === 404 && res19.body.success === false;
    record(19, "Delete another user's memory -> 404", t19Passed, `Status: ${res19.status}, Message: ${res19.body?.message}`);

    // ------------------------------------------------------------------------
    // 20. Invalid metadata -> 400
    // ------------------------------------------------------------------------
    const res20a = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Bad metadata', memoryType: 'note', metadata: ['array', 'is', 'invalid'] }
    });
    const res20b = await request(server, {
      method: 'POST',
      path: '/api/memories',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Null metadata', memoryType: 'note', metadata: null }
    });
    const t20Passed = res20a.status === 400 && res20b.status === 400;
    record(20, 'Invalid metadata -> 400', t20Passed, `Array status: ${res20a.status}, Null status: ${res20b.status}`);

    // ------------------------------------------------------------------------
    // 21. Valid metadata stored correctly
    // ------------------------------------------------------------------------
    const dbCheck = await db.query(
      'SELECT metadata FROM gaming_memories WHERE id = $1;',
      [memoryAttachedId]
    );
    const dbMetadata = dbCheck.rows[0]?.metadata;
    const t21Passed = dbMetadata && dbMetadata.ace === true && dbMetadata.kills === 30;
    record(21, 'Valid metadata stored correctly in JSONB', t21Passed, JSON.stringify(dbMetadata));

    // ------------------------------------------------------------------------
    // 22. Health endpoint still works
    // ------------------------------------------------------------------------
    const res22 = await request(server, {
      method: 'GET',
      path: '/api/health'
    });
    const t22Passed = res22.status === 200 && res22.body.success === true && res22.body.database === 'connected';
    record(22, 'Health endpoint still works -> 200', t22Passed, JSON.stringify(res22.body));

    // ------------------------------------------------------------------------
    // CLEANUP TEST DATA
    // ------------------------------------------------------------------------
    console.log('\n--- CLEANUP TEST DATA ---');
    await db.query('DELETE FROM users WHERE email IN ($1, $2);', [userAEmail, userBEmail]);
    await db.query('DELETE FROM games WHERE id = $1;', [testGameId]);
    console.log('Test users, games, sessions, and memories cleaned up.');

  } catch (error) {
    console.error('Memory test suite error:', error);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await db.pool.end();
  }

  const allPassed = results.every((r) => r.passed);
  console.log(`\n=== SUMMARY: ${results.filter((r) => r.passed).length}/${results.length} MEMORY TESTS PASSED ===`);
  process.exit(allPassed ? 0 : 1);
}

if (require.main === module) {
  runMemoryTests();
}

module.exports = { runMemoryTests };
