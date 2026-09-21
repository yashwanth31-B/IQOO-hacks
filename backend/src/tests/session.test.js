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

async function runSessionTests() {
  console.log('=== STARTING GAMING SESSION TEST SUITE ===\n');

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const testPort = server.address().port;
  console.log(`Test server running on port ${testPort}\n`);

  const timestamp = Date.now();
  const userAEmail = `player_a_${timestamp}@example.com`;
  const userBEmail = `player_b_${timestamp}@example.com`;
  const password = 'Password123!';

  let tokenA = '';
  let tokenB = '';
  let userAId = '';
  let userBId = '';
  let testGameId = '';
  let testSessionId = '';
  let userBSessionId = '';

  const results = [];

  function record(testNum, name, passed, details = '') {
    results.push({ testNum, name, passed, details });
    const mark = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${mark} [Test ${testNum}] ${name}`);
    if (details) console.log(`       ${details}`);
  }

  try {
    // ------------------------------------------------------------------------
    // SETUP: Register Users A and B
    // ------------------------------------------------------------------------
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

    // ------------------------------------------------------------------------
    // 1. Create game successfully
    // ------------------------------------------------------------------------
    const res1 = await request(server, {
      method: 'POST',
      path: '/api/games',
      body: { name: `Valorant ${timestamp}`, platform: 'PC' }
    });
    testGameId = res1.body?.game?.id;
    const t1Passed = res1.status === 201 && res1.body.success === true && !!testGameId;
    record(1, 'Create game successfully -> 201', t1Passed, `Game ID: ${testGameId}, Name: ${res1.body?.game?.name}`);

    // ------------------------------------------------------------------------
    // 2. Get games
    // ------------------------------------------------------------------------
    const res2 = await request(server, {
      method: 'GET',
      path: '/api/games'
    });
    const t2Passed = res2.status === 200 && Array.isArray(res2.body?.games) && res2.body.games.some(g => g.id === testGameId);
    record(2, 'Get games -> 200', t2Passed, `Total games found: ${res2.body?.games?.length}`);

    // ------------------------------------------------------------------------
    // 3. Create session without JWT -> 401
    // ------------------------------------------------------------------------
    const res3 = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      body: { gameId: testGameId }
    });
    const t3Passed = res3.status === 401 && res3.body.success === false;
    record(3, 'Create session without JWT -> 401', t3Passed, `Status: ${res3.status}, Message: ${res3.body?.message}`);

    // ------------------------------------------------------------------------
    // 4. Create session with invalid gameId -> 400
    // ------------------------------------------------------------------------
    const res4 = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { gameId: 'not-a-valid-uuid' }
    });
    const t4Passed = res4.status === 400 && res4.body.success === false;
    record(4, 'Create session with invalid gameId -> 400', t4Passed, `Status: ${res4.status}, Message: ${res4.body?.message}`);

    // ------------------------------------------------------------------------
    // 5. Create session with nonexistent game -> 404
    // ------------------------------------------------------------------------
    const nonExistentGameId = '00000000-0000-0000-0000-000000000000';
    const res5 = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { gameId: nonExistentGameId }
    });
    const t5Passed = res5.status === 404 && res5.body.success === false;
    record(5, 'Create session with nonexistent game -> 404', t5Passed, `Status: ${res5.status}, Message: ${res5.body?.message}`);

    // ------------------------------------------------------------------------
    // 6. Create session successfully -> 201
    // ------------------------------------------------------------------------
    const res6 = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        gameId: testGameId,
        score: 1200,
        performance: 'Good',
        notes: 'Strong first half'
      }
    });
    testSessionId = res6.body?.session?.id;
    const t6Passed = res6.status === 201 && 
      res6.body.success === true && 
      res6.body.session?.gameId === testGameId &&
      res6.body.session?.endedAt === null &&
      res6.body.session?.duration === null &&
      res6.body.session?.score === 1200;
    record(6, 'Create session successfully -> 201', t6Passed, `Session ID: ${testSessionId}`);

    // ------------------------------------------------------------------------
    // 7. Get active session -> 200
    // ------------------------------------------------------------------------
    const res7 = await request(server, {
      method: 'GET',
      path: '/api/sessions/active',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t7Passed = res7.status === 200 && res7.body.session?.id === testSessionId && res7.body.session?.endedAt === null;
    record(7, 'Get active session -> 200', t7Passed, `Active session: ${res7.body?.session?.gameName}`);

    // ------------------------------------------------------------------------
    // 8. Prevent second active session -> 409
    // ------------------------------------------------------------------------
    const res8 = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { gameId: testGameId }
    });
    const t8Passed = res8.status === 409 && res8.body.success === false;
    record(8, 'Prevent second active session -> 409', t8Passed, `Status: ${res8.status}, Message: ${res8.body?.message}`);

    // ------------------------------------------------------------------------
    // 9. Update session successfully
    // ------------------------------------------------------------------------
    const res9 = await request(server, {
      method: 'PATCH',
      path: `/api/sessions/${testSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        score: 1550,
        performance: 'Excellent',
        notes: 'Clutched round 24'
      }
    });
    const t9Passed = res9.status === 200 && 
      res9.body.session?.score === 1550 && 
      res9.body.session?.performance === 'Excellent' &&
      res9.body.session?.notes === 'Clutched round 24';
    record(9, 'Update session successfully -> 200', t9Passed, `Updated Score: ${res9.body?.session?.score}`);

    // ------------------------------------------------------------------------
    // 10. Get single session successfully
    // ------------------------------------------------------------------------
    const res10 = await request(server, {
      method: 'GET',
      path: `/api/sessions/${testSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t10Passed = res10.status === 200 && res10.body.session?.id === testSessionId;
    record(10, 'Get single session successfully -> 200', t10Passed, `Session: ${res10.body?.session?.id}`);

    // ------------------------------------------------------------------------
    // 11. Get session list successfully
    // ------------------------------------------------------------------------
    const res11 = await request(server, {
      method: 'GET',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t11Passed = res11.status === 200 && Array.isArray(res11.body?.sessions) && res11.body.sessions.length >= 1;
    record(11, 'Get session list successfully -> 200', t11Passed, `Total retrieved: ${res11.body?.sessions?.length}`);

    // ------------------------------------------------------------------------
    // 12. Pagination works
    // ------------------------------------------------------------------------
    const res12 = await request(server, {
      method: 'GET',
      path: '/api/sessions?page=1&limit=5',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const pag = res12.body?.pagination;
    const t12Passed = res12.status === 200 && pag?.page === 1 && pag?.limit === 5 && pag?.total >= 1;
    record(12, 'Pagination works -> 200', t12Passed, `Page: ${pag?.page}, Limit: ${pag?.limit}, Total: ${pag?.total}`);

    // ------------------------------------------------------------------------
    // 13. End session successfully
    // ------------------------------------------------------------------------
    // Add small delay to verify duration >= 0
    await new Promise((r) => setTimeout(r, 1000));
    const res13 = await request(server, {
      method: 'POST',
      path: `/api/sessions/${testSessionId}/end`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t13Passed = res13.status === 200 && 
      res13.body.session?.endedAt !== null && 
      typeof res13.body.session?.duration === 'number' && 
      res13.body.session?.duration >= 1;
    record(13, 'End session successfully -> 200', t13Passed, `EndedAt: ${res13.body?.session?.endedAt}, Duration: ${res13.body?.session?.duration}s`);

    // ------------------------------------------------------------------------
    // 14. Ending already-ended session -> 409
    // ------------------------------------------------------------------------
    const res14 = await request(server, {
      method: 'POST',
      path: `/api/sessions/${testSessionId}/end`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t14Passed = res14.status === 409 && res14.body.success === false;
    record(14, 'Ending already-ended session -> 409', t14Passed, `Status: ${res14.status}, Message: ${res14.body?.message}`);

    // ------------------------------------------------------------------------
    // 15. Delete session successfully
    // ------------------------------------------------------------------------
    // Create a temporary session for User A and delete it
    const tempSessionRes = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { gameId: testGameId }
    });
    const tempSessionId = tempSessionRes.body?.session?.id;

    const res15 = await request(server, {
      method: 'DELETE',
      path: `/api/sessions/${tempSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t15Passed = res15.status === 200 && res15.body.success === true;
    record(15, 'Delete session successfully -> 200', t15Passed, `Deleted session ID: ${tempSessionId}`);

    // ------------------------------------------------------------------------
    // Cross-User / Ownership setup: User B creates a session
    // ------------------------------------------------------------------------
    const resB = await request(server, {
      method: 'POST',
      path: '/api/sessions',
      headers: { Authorization: `Bearer ${tokenB}` },
      body: { gameId: testGameId, score: 999 }
    });
    userBSessionId = resB.body?.session?.id;

    // ------------------------------------------------------------------------
    // 16. Access another user's session -> 404
    // ------------------------------------------------------------------------
    const res16 = await request(server, {
      method: 'GET',
      path: `/api/sessions/${userBSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` } // User A accessing User B's session
    });
    const t16Passed = res16.status === 404 && res16.body.success === false;
    record(16, "Access another user's session -> 404", t16Passed, `Status: ${res16.status}, Message: ${res16.body?.message}`);

    // ------------------------------------------------------------------------
    // 17. Update another user's session -> 404
    // ------------------------------------------------------------------------
    const res17 = await request(server, {
      method: 'PATCH',
      path: `/api/sessions/${userBSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` }, // User A modifying User B's session
      body: { score: 9999 }
    });
    const t17Passed = res17.status === 404 && res17.body.success === false;
    record(17, "Update another user's session -> 404", t17Passed, `Status: ${res17.status}, Message: ${res17.body?.message}`);

    // ------------------------------------------------------------------------
    // 18. Delete another user's session -> 404
    // ------------------------------------------------------------------------
    const res18 = await request(server, {
      method: 'DELETE',
      path: `/api/sessions/${userBSessionId}`,
      headers: { Authorization: `Bearer ${tokenA}` } // User A deleting User B's session
    });
    const t18Passed = res18.status === 404 && res18.body.success === false;
    record(18, "Delete another user's session -> 404", t18Passed, `Status: ${res18.status}, Message: ${res18.body?.message}`);

    // ------------------------------------------------------------------------
    // 19. Invalid session UUID -> 400
    // ------------------------------------------------------------------------
    const res19 = await request(server, {
      method: 'GET',
      path: '/api/sessions/invalid-session-uuid',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t19Passed = res19.status === 400 && res19.body.success === false;
    record(19, 'Invalid session UUID -> 400', t19Passed, `Status: ${res19.status}, Message: ${res19.body?.message}`);

    // ------------------------------------------------------------------------
    // 20. Health endpoint still works
    // ------------------------------------------------------------------------
    const res20 = await request(server, {
      method: 'GET',
      path: '/api/health'
    });
    const t20Passed = res20.status === 200 && res20.body.success === true && res20.body.database === 'connected';
    record(20, 'Health endpoint still works -> 200', t20Passed, JSON.stringify(res20.body));

    // ------------------------------------------------------------------------
    // CLEANUP TEST DATA
    // ------------------------------------------------------------------------
    console.log('\n--- CLEANUP TEST DATA ---');
    await db.query('DELETE FROM users WHERE email IN ($1, $2);', [userAEmail, userBEmail]);
    await db.query('DELETE FROM games WHERE id = $1;', [testGameId]);
    console.log('Test users and test games cleaned up from database.');

  } catch (error) {
    console.error('Session test suite error:', error);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await db.pool.end();
  }

  const allPassed = results.every((r) => r.passed);
  console.log(`\n=== SUMMARY: ${results.filter((r) => r.passed).length}/${results.length} SESSION TESTS PASSED ===`);
  process.exit(allPassed ? 0 : 1);
}

if (require.main === module) {
  runSessionTests();
}

module.exports = { runSessionTests };
