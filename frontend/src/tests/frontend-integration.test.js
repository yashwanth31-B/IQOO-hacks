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

    // Clean up test user in PostgreSQL
    console.log('\n--- CLEANING UP TEST USER ---');
    await db.query('DELETE FROM users WHERE email = $1;', [testUserEmail]);
    console.log(`Cleaned up ${testUserEmail} from database.`);

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
