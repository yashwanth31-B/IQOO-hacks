const db = require('../db');

/**
 * Format raw task row into clean camelCase object
 * @param {Object} row 
 * @returns {Object}
 */
const formatTask = (row) => ({
  id: row.id,
  userId: row.user_id,
  title: row.title,
  description: row.description || null,
  priority: row.priority || 'medium',
  dueDate: row.due_date ? new Date(row.due_date).toISOString() : null,
  estimatedMinutes: row.estimated_minutes !== null && row.estimated_minutes !== undefined ? Number(row.estimated_minutes) : null,
  completed: Boolean(row.completed),
  createdAt: row.created_at,
  updatedAt: row.updated_at
});

/**
 * Create a new task for the authenticated user
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const createTask = async ({ userId, title, description, priority, dueDate, estimatedMinutes }) => {
  const trimmedTitle = title.trim();
  const trimmedDescription = description && typeof description === 'string' ? description.trim() : null;
  const cleanPriority = priority && typeof priority === 'string' ? priority.trim().toLowerCase() : 'medium';
  const cleanDueDate = dueDate ? new Date(dueDate).toISOString() : null;
  const cleanMins = estimatedMinutes !== undefined && estimatedMinutes !== null ? parseInt(estimatedMinutes, 10) : null;

  const result = await db.query(
    `INSERT INTO tasks (user_id, title, description, priority, due_date, estimated_minutes, completed)
     VALUES ($1, $2, $3, $4, $5, $6, FALSE)
     RETURNING id, user_id, title, description, priority, due_date, estimated_minutes, completed, created_at, updated_at;`,
    [userId, trimmedTitle, trimmedDescription, cleanPriority, cleanDueDate, cleanMins]
  );

  return formatTask(result.rows[0]);
};

/**
 * Retrieve paginated tasks for authenticated user with optional filtering
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getTasks = async ({ userId, page, limit, completed, priority }) => {
  const offset = (page - 1) * limit;

  const whereClauses = ['user_id = $1'];
  const queryParams = [userId];
  let paramIndex = 2;

  if (completed !== undefined) {
    whereClauses.push(`completed = $${paramIndex++}`);
    queryParams.push(completed);
  }

  if (priority !== undefined) {
    whereClauses.push(`priority = $${paramIndex++}`);
    queryParams.push(priority.trim().toLowerCase());
  }

  const whereSql = whereClauses.join(' AND ');

  // 1. Total count
  const countResult = await db.query(
    `SELECT COUNT(*)::integer AS total FROM tasks WHERE ${whereSql};`,
    queryParams
  );
  const total = countResult.rows[0].total;
  const totalPages = Math.ceil(total / limit);

  // 2. Paginated rows
  const listParams = [...queryParams, limit, offset];
  const listResult = await db.query(
    `SELECT id, user_id, title, description, priority, due_date, estimated_minutes, completed, created_at, updated_at
     FROM tasks
     WHERE ${whereSql}
     ORDER BY created_at DESC
     LIMIT $${paramIndex++} OFFSET $${paramIndex++};`,
    listParams
  );

  const formattedRows = listResult.rows.map(formatTask);

  return {
    tasks: formattedRows,
    data: formattedRows, // Provide both 'tasks' and 'data' for maximum compatibility
    pagination: {
      page,
      limit,
      total,
      totalPages
    }
  };
};

/**
 * Retrieve a single task by ID for authenticated user
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const getTaskById = async ({ taskId, userId }) => {
  const result = await db.query(
    `SELECT id, user_id, title, description, priority, due_date, estimated_minutes, completed, created_at, updated_at
     FROM tasks
     WHERE id = $1 AND user_id = $2;`,
    [taskId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Task not found');
    error.statusCode = 404;
    throw error;
  }

  return formatTask(result.rows[0]);
};

/**
 * Update task fields for authenticated user
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const updateTask = async ({ taskId, userId, updates }) => {
  // 1. Verify existence & ownership
  const checkResult = await db.query(
    'SELECT id FROM tasks WHERE id = $1 AND user_id = $2;',
    [taskId, userId]
  );

  if (checkResult.rows.length === 0) {
    const error = new Error('Task not found');
    error.statusCode = 404;
    throw error;
  }

  // 2. Build dynamic update
  const setClauses = [];
  const queryParams = [taskId, userId];
  let paramIndex = 3;

  if (updates.title !== undefined) {
    setClauses.push(`title = $${paramIndex++}`);
    queryParams.push(updates.title.trim());
  }

  if (updates.description !== undefined) {
    setClauses.push(`description = $${paramIndex++}`);
    queryParams.push(typeof updates.description === 'string' ? updates.description.trim() : null);
  }

  if (updates.priority !== undefined) {
    setClauses.push(`priority = $${paramIndex++}`);
    queryParams.push(updates.priority.trim().toLowerCase());
  }

  if (updates.dueDate !== undefined) {
    setClauses.push(`due_date = $${paramIndex++}`);
    queryParams.push(updates.dueDate ? new Date(updates.dueDate).toISOString() : null);
  }

  if (updates.estimatedMinutes !== undefined) {
    setClauses.push(`estimated_minutes = $${paramIndex++}`);
    queryParams.push(updates.estimatedMinutes !== null ? parseInt(updates.estimatedMinutes, 10) : null);
  }

  if (updates.completed !== undefined) {
    setClauses.push(`completed = $${paramIndex++}`);
    queryParams.push(Boolean(updates.completed));
  }

  setClauses.push('updated_at = CURRENT_TIMESTAMP');

  const updateSql = `
    UPDATE tasks
    SET ${setClauses.join(', ')}
    WHERE id = $1 AND user_id = $2
    RETURNING id, user_id, title, description, priority, due_date, estimated_minutes, completed, created_at, updated_at;
  `;

  const updateResult = await db.query(updateSql, queryParams);
  return formatTask(updateResult.rows[0]);
};

/**
 * Mark a task as completed or incomplete
 * @param {Object} param0 
 * @returns {Promise<Object>}
 */
const setTaskCompletion = async ({ taskId, userId, completed }) => {
  const result = await db.query(
    `UPDATE tasks
     SET completed = $3,
         updated_at = CURRENT_TIMESTAMP
     WHERE id = $1 AND user_id = $2
     RETURNING id, user_id, title, description, priority, due_date, estimated_minutes, completed, created_at, updated_at;`,
    [taskId, userId, Boolean(completed)]
  );

  if (result.rows.length === 0) {
    const error = new Error('Task not found');
    error.statusCode = 404;
    throw error;
  }

  return formatTask(result.rows[0]);
};

/**
 * Delete a task for authenticated user
 * @param {Object} param0 
 * @returns {Promise<void>}
 */
const deleteTask = async ({ taskId, userId }) => {
  const result = await db.query(
    'DELETE FROM tasks WHERE id = $1 AND user_id = $2 RETURNING id;',
    [taskId, userId]
  );

  if (result.rows.length === 0) {
    const error = new Error('Task not found');
    error.statusCode = 404;
    throw error;
  }
};

module.exports = {
  createTask,
  getTasks,
  getTaskById,
  updateTask,
  setTaskCompletion,
  deleteTask
};
