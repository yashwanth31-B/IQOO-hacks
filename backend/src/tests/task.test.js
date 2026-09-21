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

async function runTaskTests() {
  console.log('=== STARTING PRODUCTIVITY / TASK TEST SUITE ===\n');

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const testPort = server.address().port;
  console.log(`Test server running on port ${testPort}\n`);

  const timestamp = Date.now();
  const userAEmail = `task_user_a_${timestamp}@example.com`;
  const userBEmail = `task_user_b_${timestamp}@example.com`;
  const password = 'Password123!';

  let tokenA = '';
  let tokenB = '';
  let userAId = '';
  let userBId = '';
  let taskA1Id = '';
  let taskA2Id = '';
  let taskB1Id = '';

  const results = [];

  function record(testNum, name, passed, details = '') {
    results.push({ testNum, name, passed, details });
    const mark = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${mark} [Test ${testNum}] ${name}`);
    if (details) console.log(`       ${details}`);
  }

  try {
    // ------------------------------------------------------------------------
    // SETUP: Users A and B
    // ------------------------------------------------------------------------
    const regA = await request(server, {
      method: 'POST',
      path: '/api/auth/signup',
      body: { name: 'Task User A', email: userAEmail, password }
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
      body: { name: 'Task User B', email: userBEmail, password }
    });
    userBId = regB.body?.user?.id;

    const loginB = await request(server, {
      method: 'POST',
      path: '/api/auth/login',
      body: { email: userBEmail, password }
    });
    tokenB = loginB.body?.token;

    // ------------------------------------------------------------------------
    // 1. Create task successfully with all valid fields -> 201
    // ------------------------------------------------------------------------
    const res1 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Review Aim Routine',
        description: 'Spend 20 minutes in Kovaaks before competitive match',
        priority: 'high',
        dueDate: '2026-10-01T15:00:00.000Z',
        estimatedMinutes: 20
      }
    });
    const t1Passed =
      res1.status === 201 &&
      res1.body.success === true &&
      res1.body.task?.id &&
      res1.body.task.title === 'Review Aim Routine' &&
      res1.body.task.priority === 'high' &&
      res1.body.task.estimatedMinutes === 20 &&
      res1.body.task.completed === false;
    taskA1Id = res1.body?.task?.id;
    record(1, 'Create task successfully -> 201', t1Passed, `Task ID: ${taskA1Id}`);

    // ------------------------------------------------------------------------
    // 2. Create task without JWT -> 401
    // ------------------------------------------------------------------------
    const res2 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      body: { title: 'No token task' }
    });
    const t2Passed = res2.status === 401 && res2.body.success === false;
    record(2, 'Create task without JWT -> 401', t2Passed, `Status: ${res2.status}, Message: ${res2.body.message}`);

    // ------------------------------------------------------------------------
    // 3. Create task with missing title -> 400
    // ------------------------------------------------------------------------
    const res3 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { description: 'Missing title' }
    });
    const t3Passed = res3.status === 400 && res3.body.message === 'Title is required';
    record(3, 'Create task with missing title -> 400', t3Passed, `Message: ${res3.body.message}`);

    // ------------------------------------------------------------------------
    // 4. Create task with empty string title -> 400
    // ------------------------------------------------------------------------
    const res4 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: '   ' }
    });
    const t4Passed = res4.status === 400 && res4.body.message === 'Title is required';
    record(4, 'Create task with empty title -> 400', t4Passed, `Message: ${res4.body.message}`);

    // ------------------------------------------------------------------------
    // 5. Create task with invalid priority -> 400
    // ------------------------------------------------------------------------
    const res5 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Invalid Priority Task', priority: 'urgent' }
    });
    const t5Passed = res5.status === 400 && res5.body.message?.includes('Priority must be one of');
    record(5, 'Create task with invalid priority -> 400', t5Passed, `Message: ${res5.body.message}`);

    // ------------------------------------------------------------------------
    // 6. Create task with invalid due date -> 400
    // ------------------------------------------------------------------------
    const res6 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Invalid Due Date Task', dueDate: 'not-a-valid-date' }
    });
    const t6Passed = res6.status === 400 && res6.body.message?.includes('due date');
    record(6, 'Create task with invalid due date -> 400', t6Passed, `Message: ${res6.body.message}`);

    // ------------------------------------------------------------------------
    // 7. Create task with invalid estimatedMinutes -> 400
    // ------------------------------------------------------------------------
    const res7 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Invalid Mins Task', estimatedMinutes: -10 }
    });
    const t7Passed = res7.status === 400 && res7.body.message?.includes('Estimated minutes');
    record(7, 'Create task with invalid estimatedMinutes -> 400', t7Passed, `Message: ${res7.body.message}`);

    // ------------------------------------------------------------------------
    // 8. Create minimal task (only title, default priority 'medium', completed false) -> 201
    // ------------------------------------------------------------------------
    const res8 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Study Agent Lineups' }
    });
    const t8Passed =
      res8.status === 201 &&
      res8.body.task?.id &&
      res8.body.task.priority === 'medium' &&
      res8.body.task.completed === false;
    taskA2Id = res8.body?.task?.id;
    record(8, 'Create minimal task with defaults -> 201', t8Passed, `Priority: ${res8.body?.task?.priority}, Completed: ${res8.body?.task?.completed}`);

    // ------------------------------------------------------------------------
    // User B creates a task (to test IDOR isolation)
    // ------------------------------------------------------------------------
    const resB = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenB}` },
      body: { title: "User B's Private Task", priority: 'low' }
    });
    taskB1Id = resB.body?.task?.id;

    // ------------------------------------------------------------------------
    // 9. Get tasks list for authenticated user -> 200
    // ------------------------------------------------------------------------
    const res9 = await request(server, {
      method: 'GET',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t9Passed =
      res9.status === 200 &&
      res9.body.success === true &&
      Array.isArray(res9.body.tasks) &&
      res9.body.tasks.length === 2 &&
      res9.body.pagination?.total === 2 &&
      !res9.body.tasks.some((t) => t.id === taskB1Id); // Does not leak User B's task
    record(9, 'Get tasks list scoped to user -> 200', t9Passed, `Found: ${res9.body.tasks?.length} tasks for User A`);

    // ------------------------------------------------------------------------
    // 10. Get tasks pagination -> 200
    // ------------------------------------------------------------------------
    const res10 = await request(server, {
      method: 'GET',
      path: '/api/tasks?page=1&limit=1',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t10Passed =
      res10.status === 200 &&
      res10.body.tasks.length === 1 &&
      res10.body.pagination?.page === 1 &&
      res10.body.pagination?.limit === 1 &&
      res10.body.pagination?.total === 2 &&
      res10.body.pagination?.totalPages === 2;
    record(10, 'Pagination (?page=1&limit=1) -> 200', t10Passed, `Page: ${res10.body.pagination?.page}, TotalPages: ${res10.body.pagination?.totalPages}`);

    // ------------------------------------------------------------------------
    // Setup for filter tests: Mark taskA1 completed
    // ------------------------------------------------------------------------
    await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskA1Id}/complete`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });

    // ------------------------------------------------------------------------
    // 11. Get tasks filter completed=true -> 200
    // ------------------------------------------------------------------------
    const res11 = await request(server, {
      method: 'GET',
      path: '/api/tasks?completed=true',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t11Passed =
      res11.status === 200 &&
      res11.body.tasks.length === 1 &&
      res11.body.tasks[0].id === taskA1Id &&
      res11.body.tasks[0].completed === true;
    record(11, 'Filter tasks by completed=true -> 200', t11Passed, `Matches: ${res11.body.tasks?.length}`);

    // ------------------------------------------------------------------------
    // 12. Get tasks filter completed=false -> 200
    // ------------------------------------------------------------------------
    const res12 = await request(server, {
      method: 'GET',
      path: '/api/tasks?completed=false',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t12Passed =
      res12.status === 200 &&
      res12.body.tasks.length === 1 &&
      res12.body.tasks[0].id === taskA2Id &&
      res12.body.tasks[0].completed === false;
    record(12, 'Filter tasks by completed=false -> 200', t12Passed, `Matches: ${res12.body.tasks?.length}`);

    // ------------------------------------------------------------------------
    // 13. Get tasks filter priority=high -> 200
    // ------------------------------------------------------------------------
    const res13 = await request(server, {
      method: 'GET',
      path: '/api/tasks?priority=high',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t13Passed =
      res13.status === 200 &&
      res13.body.tasks.length === 1 &&
      res13.body.tasks[0].id === taskA1Id &&
      res13.body.tasks[0].priority === 'high';
    record(13, 'Filter tasks by priority=high -> 200', t13Passed, `Matches: ${res13.body.tasks?.length}`);

    // ------------------------------------------------------------------------
    // 14. Get tasks filter combined completed=false&priority=medium -> 200
    // ------------------------------------------------------------------------
    const res14 = await request(server, {
      method: 'GET',
      path: '/api/tasks?completed=false&priority=medium',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t14Passed =
      res14.status === 200 &&
      res14.body.tasks.length === 1 &&
      res14.body.tasks[0].id === taskA2Id;
    record(14, 'Combined filter (completed=false&priority=medium) -> 200', t14Passed, `Matches: ${res14.body.tasks?.length}`);

    // ------------------------------------------------------------------------
    // 15. Invalid completed query parameter -> 400
    // ------------------------------------------------------------------------
    const res15 = await request(server, {
      method: 'GET',
      path: '/api/tasks?completed=invalid',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t15Passed = res15.status === 400 && res15.body.message?.includes('completed');
    record(15, 'Invalid completed query parameter -> 400', t15Passed, `Message: ${res15.body.message}`);

    // ------------------------------------------------------------------------
    // 16. Invalid priority query parameter -> 400
    // ------------------------------------------------------------------------
    const res16 = await request(server, {
      method: 'GET',
      path: '/api/tasks?priority=superurgent',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t16Passed = res16.status === 400 && res16.body.message?.includes('priority');
    record(16, 'Invalid priority query parameter -> 400', t16Passed, `Message: ${res16.body.message}`);

    // ------------------------------------------------------------------------
    // 17. Get single task by ID -> 200
    // ------------------------------------------------------------------------
    const res17 = await request(server, {
      method: 'GET',
      path: `/api/tasks/${taskA1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t17Passed =
      res17.status === 200 &&
      res17.body.success === true &&
      res17.body.task?.id === taskA1Id &&
      res17.body.task?.userId === userAId;
    record(17, 'Get single task by ID -> 200', t17Passed, `Task: ${res17.body.task?.title}`);

    // ------------------------------------------------------------------------
    // 18. Get single task with invalid UUID -> 400
    // ------------------------------------------------------------------------
    const res18 = await request(server, {
      method: 'GET',
      path: '/api/tasks/not-a-valid-uuid',
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t18Passed = res18.status === 400 && res18.body.message?.includes('valid UUID');
    record(18, 'Get task with invalid UUID -> 400', t18Passed, `Message: ${res18.body.message}`);

    // ------------------------------------------------------------------------
    // 19. Get another user's task -> 404 (IDOR protection)
    // ------------------------------------------------------------------------
    const res19 = await request(server, {
      method: 'GET',
      path: `/api/tasks/${taskB1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t19Passed = res19.status === 404 && res19.body.message === 'Task not found';
    record(19, "Get another user's task -> 404 (IDOR protected)", t19Passed, `Message: ${res19.body.message}`);

    // ------------------------------------------------------------------------
    // 20. Update own task -> 200
    // ------------------------------------------------------------------------
    const res20 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskA1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: 'Updated Aim Routine',
        description: 'Updated 30 minutes in Kovaaks',
        priority: 'medium',
        estimatedMinutes: 30
      }
    });
    const t20Passed =
      res20.status === 200 &&
      res20.body.success === true &&
      res20.body.task?.title === 'Updated Aim Routine' &&
      res20.body.task?.priority === 'medium' &&
      res20.body.task?.estimatedMinutes === 30;
    record(20, 'Update own task -> 200', t20Passed, `Updated Title: ${res20.body.task?.title}`);

    // ------------------------------------------------------------------------
    // 21. Update task with disallowed/read-only field (userId, id) -> 400
    // ------------------------------------------------------------------------
    const res21 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskA1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { userId: userBId }
    });
    const t21Passed = res21.status === 400 && res21.body.message?.includes('cannot be modified');
    record(21, 'Update task with disallowed field -> 400', t21Passed, `Message: ${res21.body.message}`);

    // ------------------------------------------------------------------------
    // 22. Update another user's task -> 404 (IDOR protection)
    // ------------------------------------------------------------------------
    const res22 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskB1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` },
      body: { title: 'Malicious title overwrite' }
    });
    const t22Passed = res22.status === 404 && res22.body.message === 'Task not found';
    record(22, "Update another user's task -> 404 (IDOR protected)", t22Passed, `Message: ${res22.body.message}`);

    // ------------------------------------------------------------------------
    // 23. Mark task as completed (PATCH /api/tasks/:id/complete) -> 200
    // ------------------------------------------------------------------------
    const res23 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskA2Id}/complete`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t23Passed =
      res23.status === 200 &&
      res23.body.success === true &&
      res23.body.task?.completed === true &&
      res23.body.message === 'Task marked as completed';
    record(23, 'Mark own task completed -> 200', t23Passed, `Completed: ${res23.body.task?.completed}`);

    // ------------------------------------------------------------------------
    // 24. Mark task as incomplete (PATCH /api/tasks/:id/incomplete) -> 200
    // ------------------------------------------------------------------------
    const res24 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskA2Id}/incomplete`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t24Passed =
      res24.status === 200 &&
      res24.body.success === true &&
      res24.body.task?.completed === false &&
      res24.body.message === 'Task marked as incomplete';
    record(24, 'Mark own task incomplete -> 200', t24Passed, `Completed: ${res24.body.task?.completed}`);

    // ------------------------------------------------------------------------
    // 25. Complete another user's task -> 404 (IDOR protection)
    // ------------------------------------------------------------------------
    const res25 = await request(server, {
      method: 'PATCH',
      path: `/api/tasks/${taskB1Id}/complete`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t25Passed = res25.status === 404 && res25.body.message === 'Task not found';
    record(25, "Complete another user's task -> 404 (IDOR protected)", t25Passed, `Message: ${res25.body.message}`);

    // ------------------------------------------------------------------------
    // 26. Delete own task -> 200
    // ------------------------------------------------------------------------
    const res26 = await request(server, {
      method: 'DELETE',
      path: `/api/tasks/${taskA1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t26Passed = res26.status === 200 && res26.body.success === true;
    record(26, 'Delete own task -> 200', t26Passed, `Deleted task: ${taskA1Id}`);

    // Verify it is really gone
    const verifyDel = await request(server, {
      method: 'GET',
      path: `/api/tasks/${taskA1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const verifyDelPassed = verifyDel.status === 404;
    record(27, 'Verify deleted task is gone -> 404', verifyDelPassed, `Status: ${verifyDel.status}`);

    // ------------------------------------------------------------------------
    // 28. Delete another user's task -> 404 (IDOR protection)
    // ------------------------------------------------------------------------
    const res28 = await request(server, {
      method: 'DELETE',
      path: `/api/tasks/${taskB1Id}`,
      headers: { Authorization: `Bearer ${tokenA}` }
    });
    const t28Passed = res28.status === 404 && res28.body.message === 'Task not found';
    record(28, "Delete another user's task -> 404 (IDOR protected)", t28Passed, `Message: ${res28.body.message}`);

    // ------------------------------------------------------------------------
    // 29. Parameterized SQL safety check (SQL Injection attempt) -> 201
    // ------------------------------------------------------------------------
    const sqlInjectionPayload = "'; DROP TABLE tasks; --";
    const res29 = await request(server, {
      method: 'POST',
      path: '/api/tasks',
      headers: { Authorization: `Bearer ${tokenA}` },
      body: {
        title: sqlInjectionPayload,
        description: "Test description'; DELETE FROM users; --",
        priority: 'high'
      }
    });
    const t29Passed =
      res29.status === 201 &&
      res29.body.task?.title === sqlInjectionPayload;
    record(29, 'Parameterized SQL injection safety -> 201', t29Passed, `Stored literal text safely`);

    // ------------------------------------------------------------------------
    // 30. Health endpoint still works
    // ------------------------------------------------------------------------
    const res30 = await request(server, {
      method: 'GET',
      path: '/api/health'
    });
    const t30Passed =
      res30.status === 200 &&
      res30.body.success === true &&
      res30.body.database === 'connected';
    record(30, 'Health endpoint still works -> 200', t30Passed, JSON.stringify(res30.body));

    // ------------------------------------------------------------------------
    // CLEANUP TEST DATA
    // ------------------------------------------------------------------------
    console.log('\n--- CLEANUP TEST DATA ---');
    await db.query('DELETE FROM users WHERE email IN ($1, $2);', [userAEmail, userBEmail]);
    console.log('Test users and tasks cleaned up.');

  } catch (error) {
    console.error('Task test suite error:', error);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await db.pool.end();
  }

  const allPassed = results.every((r) => r.passed);
  console.log(`\n=== SUMMARY: ${results.filter((r) => r.passed).length}/${results.length} TASK TESTS PASSED ===`);
  process.exit(allPassed ? 0 : 1);
}

if (require.main === module) {
  runTaskTests();
}

module.exports = { runTaskTests };
