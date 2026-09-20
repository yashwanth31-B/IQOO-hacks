const http = require('http');
const jwt = require('jsonwebtoken');
const app = require('../server');
const db = require('../db');

// Helper to make HTTP requests against the in-memory/listening server
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

async function runTests() {
  console.log('=== STARTING AUTHENTICATION SUITE TESTS ===\n');

  // Start test server on random free port
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const testPort = server.address().port;
  console.log(`Test server running on port ${testPort}\n`);

  const testEmail = `test_player_${Date.now()}@example.com`;
  const testPassword = 'SecurePassword123!';
  const testName = 'Lokesh Test';
  let validToken = '';
  let testUserId = '';

  const results = [];

  function record(testNumber, name, passed, details = '') {
    results.push({ testNumber, name, passed, details });
    const mark = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${mark} [Test ${testNumber}] ${name}`);
    if (details) console.log(`       ${details}`);
  }

  try {
    // ------------------------------------------------------------------------
    // SIGNUP TESTS
    // ------------------------------------------------------------------------
    console.log('--- SIGNUP TESTS ---');

    // Test 1: Valid signup -> success (201)
    const res1 = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: testName, email: testEmail, password: testPassword }
    });
    const t1Passed = res1.status === 201 && res1.body.success === true && res1.body.user && !res1.body.user.password_hash;
    testUserId = res1.body?.user?.id;
    record(1, 'Valid signup -> success (201)', t1Passed, `Status: ${res1.status}, User ID: ${testUserId}`);

    // Test 2: Duplicate email -> rejected (409)
    const res2 = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Duplicate Player', email: testEmail, password: 'AnotherPassword123!' }
    });
    const t2Passed = res2.status === 409 && res2.body.success === false;
    record(2, 'Duplicate email -> rejected (409)', t2Passed, `Status: ${res2.status}, Message: ${res2.body?.message}`);

    // Test 3: Missing name -> rejected (400)
    const res3 = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { email: `other_${Date.now()}@example.com`, password: testPassword }
    });
    const t3Passed = res3.status === 400 && res3.body.success === false;
    record(3, 'Missing name -> rejected (400)', t3Passed, `Status: ${res3.status}, Message: ${res3.body?.message}`);

    // Test 4: Invalid email -> rejected (400)
    const res4 = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Bad Email User', email: 'not-a-valid-email', password: testPassword }
    });
    const t4Passed = res4.status === 400 && res4.body.success === false;
    record(4, 'Invalid email -> rejected (400)', t4Passed, `Status: ${res4.status}, Message: ${res4.body?.message}`);

    // Test 5: Weak/invalid password -> rejected (400)
    const res5 = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Weak Pass User', email: `weak_${Date.now()}@example.com`, password: '123' }
    });
    const t5Passed = res5.status === 400 && res5.body.success === false;
    record(5, 'Weak/invalid password (< 6 chars) -> rejected (400)', t5Passed, `Status: ${res5.status}, Message: ${res5.body?.message}`);

    // ------------------------------------------------------------------------
    // LOGIN TESTS
    // ------------------------------------------------------------------------
    console.log('\n--- LOGIN TESTS ---');

    // Test 6: Valid credentials -> JWT returned (200)
    const res6 = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: testEmail, password: testPassword }
    });
    validToken = res6.body?.token;
    const t6Passed = res6.status === 200 && res6.body.success === true && !!validToken && !res6.body.user?.password_hash;
    record(6, 'Valid credentials -> JWT returned (200)', t6Passed, `Status: ${res6.status}, Token length: ${validToken?.length}`);

    // Test 7: Wrong password -> rejected (401)
    const res7 = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: testEmail, password: 'WrongPassword999!' }
    });
    const t7Passed = res7.status === 401 && res7.body.success === false;
    record(7, 'Wrong password -> rejected (401)', t7Passed, `Status: ${res7.status}, Message: ${res7.body?.message}`);

    // Test 8: Unknown email -> rejected (401)
    const res8 = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: 'nonexistent_gamer@example.com', password: testPassword }
    });
    const t8Passed = res8.status === 401 && res8.body.success === false;
    record(8, 'Unknown email -> rejected (401)', t8Passed, `Status: ${res8.status}, Message: ${res8.body?.message}`);

    // Test 9: Missing fields -> rejected (400)
    const res9 = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: testEmail }
    });
    const t9Passed = res9.status === 400 && res9.body.success === false;
    record(9, 'Missing fields -> rejected (400)', t9Passed, `Status: ${res9.status}, Message: ${res9.body?.message}`);

    // ------------------------------------------------------------------------
    // PROTECTED ENDPOINT TESTS
    // ------------------------------------------------------------------------
    console.log('\n--- PROTECTED ENDPOINT TESTS (/api/auth/me) ---');

    // Test 10: Valid JWT -> /api/auth/me succeeds (200)
    const res10 = await request(server, {
      method: 'GET',
      path: '/api/auth/me',
      headers: { Authorization: `Bearer ${validToken}` }
    });
    const t10Passed = res10.status === 200 && res10.body.success === true && res10.body.user?.email === testEmail && !res10.body.user?.password_hash;
    record(10, 'Valid JWT -> /api/auth/me succeeds (200)', t10Passed, `User: ${res10.body?.user?.name} (${res10.body?.user?.email})`);

    // Test 11: Missing JWT -> 401
    const res11 = await request(server, {
      method: 'GET',
      path: '/api/auth/me'
    });
    const t11Passed = res11.status === 401 && res11.body.success === false;
    record(11, 'Missing JWT -> 401', t11Passed, `Status: ${res11.status}, Message: ${res11.body?.message}`);

    // Test 12: Invalid JWT -> 401
    const res12 = await request(server, {
      method: 'GET',
      path: '/api/auth/me',
      headers: { Authorization: 'Bearer invalid.token.signature' }
    });
    const t12Passed = res12.status === 401 && res12.body.success === false;
    record(12, 'Invalid JWT -> 401', t12Passed, `Status: ${res12.status}, Message: ${res12.body?.message}`);

    // Test 13: Expired JWT -> 401
    const expiredToken = jwt.sign(
      { userId: testUserId, email: testEmail },
      process.env.JWT_SECRET,
      { expiresIn: -10 } // Already expired
    );
    const res13 = await request(server, {
      method: 'GET',
      path: '/api/auth/me',
      headers: { Authorization: `Bearer ${expiredToken}` }
    });
    const t13Passed = res13.status === 401 && res13.body.message === 'Authentication token expired';
    record(13, 'Expired JWT -> 401', t13Passed, `Status: ${res13.status}, Message: ${res13.body?.message}`);

    // ------------------------------------------------------------------------
    // DATABASE VERIFICATION
    // ------------------------------------------------------------------------
    console.log('\n--- DATABASE VERIFICATION ---');
    const dbUserRes = await db.query(
      'SELECT id, name, email, password_hash, created_at FROM users WHERE id = $1;',
      [testUserId]
    );

    const dbUser = dbUserRes.rows[0];
    const isBcrypt = dbUser.password_hash.startsWith('$2a$') || dbUser.password_hash.startsWith('$2b$');
    const noPlaintext = !Object.values(dbUser).includes(testPassword);

    console.log(`[DB Check] User in DB ID: ${dbUser.id}`);
    console.log(`[DB Check] Stored password_hash starts with: ${dbUser.password_hash.substring(0, 10)}... (Valid bcrypt hash: ${isBcrypt})`);
    console.log(`[DB Check] Plaintext password exists in row: ${!noPlaintext}`);

    const dbCheckPassed = isBcrypt && noPlaintext && dbUser.email === testEmail;
    record(14, 'Database verification: hash stored, plaintext excluded', dbCheckPassed);

    // ------------------------------------------------------------------------
    // HEALTH CHECK CONTINUITY
    // ------------------------------------------------------------------------
    console.log('\n--- HEALTH CHECK VERIFICATION ---');
    const healthRes = await request(server, {
      method: 'GET',
      path: '/api/health'
    });
    const healthPassed = healthRes.status === 200 && healthRes.body.success === true && healthRes.body.database === 'connected';
    record(15, 'GET /api/health continuity -> 200 and DB connected', healthPassed, JSON.stringify(healthRes.body));

    // ------------------------------------------------------------------------
    // CLEANUP
    // ------------------------------------------------------------------------
    console.log('\n--- CLEANUP TEST DATA ---');
    await db.query('DELETE FROM users WHERE email = $1;', [testEmail]);
    console.log(`Test user ${testEmail} removed from database.`);

  } catch (err) {
    console.error('Test execution error:', err);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await db.pool.end();
  }

  const allPassed = results.every((r) => r.passed);
  console.log(`\n=== SUMMARY: ${results.filter((r) => r.passed).length}/${results.length} TESTS PASSED ===`);
  process.exit(allPassed ? 0 : 1);
}

if (require.main === module) {
  runTests();
}

module.exports = { runTests };
