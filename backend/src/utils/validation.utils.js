/**
 * Validation utilities for authentication, games, gaming sessions, memories, and tasks
 */

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MIN_PASSWORD_LENGTH = 6;
const ALLOWED_PRIORITIES = ['low', 'medium', 'high'];

/**
 * Validate email format
 * @param {string} email 
 * @returns {boolean}
 */
const isValidEmail = (email) => {
  if (typeof email !== 'string') return false;
  return EMAIL_REGEX.test(email.trim());
};

/**
 * Normalize email by trimming and converting to lowercase
 * @param {string} email 
 * @returns {string}
 */
const normalizeEmail = (email) => {
  return typeof email === 'string' ? email.trim().toLowerCase() : '';
};

/**
 * Validate UUID string format
 * @param {string} uuid 
 * @returns {boolean}
 */
const isValidUUID = (uuid) => {
  if (typeof uuid !== 'string') return false;
  return UUID_REGEX.test(uuid.trim());
};

/**
 * Validate plain JSON object for metadata
 * @param {*} metadata 
 * @returns {boolean}
 */
const isValidMetadata = (metadata) => {
  if (typeof metadata !== 'object' || metadata === null || Array.isArray(metadata)) {
    return false;
  }
  return true;
};

/**
 * Validate date format (ISO 8601 or parseable date string)
 * @param {*} dateVal 
 * @returns {boolean}
 */
const isValidDate = (dateVal) => {
  if (typeof dateVal !== 'string' || dateVal.trim().length === 0) return false;
  const parsed = Date.parse(dateVal);
  return !isNaN(parsed);
};

/**
 * Validate signup payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateSignupInput = ({ name, email, password }) => {
  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return { isValid: false, error: 'Name is required' };
  }

  if (name.trim().length > 255) {
    return { isValid: false, error: 'Name must not exceed 255 characters' };
  }

  if (!email || typeof email !== 'string' || email.trim().length === 0) {
    return { isValid: false, error: 'Email is required' };
  }

  if (!isValidEmail(email)) {
    return { isValid: false, error: 'Invalid email format' };
  }

  if (!password || typeof password !== 'string') {
    return { isValid: false, error: 'Password is required' };
  }

  if (password.length < MIN_PASSWORD_LENGTH) {
    return { 
      isValid: false, 
      error: `Password must be at least ${MIN_PASSWORD_LENGTH} characters long` 
    };
  }

  return { isValid: true };
};

/**
 * Validate login payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateLoginInput = ({ email, password }) => {
  if (!email || typeof email !== 'string' || email.trim().length === 0) {
    return { isValid: false, error: 'Email is required' };
  }

  if (!isValidEmail(email)) {
    return { isValid: false, error: 'Invalid email format' };
  }

  if (!password || typeof password !== 'string' || password.length === 0) {
    return { isValid: false, error: 'Password is required' };
  }

  return { isValid: true };
};

/**
 * Validate game creation payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateGameInput = ({ name, platform }) => {
  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return { isValid: false, error: 'Game name is required' };
  }

  if (name.trim().length > 255) {
    return { isValid: false, error: 'Game name must not exceed 255 characters' };
  }

  if (platform !== undefined && platform !== null) {
    if (typeof platform !== 'string') {
      return { isValid: false, error: 'Platform must be a string' };
    }
    if (platform.trim().length > 100) {
      return { isValid: false, error: 'Platform must not exceed 100 characters' };
    }
  }

  return { isValid: true };
};

/**
 * Validate session creation payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateCreateSessionInput = ({ gameId, score, performance, notes }) => {
  if (!gameId || typeof gameId !== 'string' || !isValidUUID(gameId)) {
    return { isValid: false, error: 'Valid gameId (UUID) is required' };
  }

  if (score !== undefined && score !== null) {
    const numScore = Number(score);
    if (isNaN(numScore) || !isFinite(numScore)) {
      return { isValid: false, error: 'Score must be a valid numeric value' };
    }
  }

  if (performance !== undefined && performance !== null) {
    if (typeof performance !== 'string') {
      return { isValid: false, error: 'Performance must be a string' };
    }
    if (performance.trim().length > 255) {
      return { isValid: false, error: 'Performance must not exceed 255 characters' };
    }
  }

  if (notes !== undefined && notes !== null) {
    if (typeof notes !== 'string') {
      return { isValid: false, error: 'Notes must be a string' };
    }
    if (notes.trim().length > 5000) {
      return { isValid: false, error: 'Notes must not exceed 5000 characters' };
    }
  }

  return { isValid: true };
};

/**
 * Validate session update payload
 * @param {Object} body 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateUpdateSessionInput = (body) => {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { isValid: false, error: 'Request body must be an object' };
  }

  // Check for disallowed modifications
  const disallowedFields = [
    'id', 'userId', 'user_id', 'gameId', 'game_id', 
    'startedAt', 'started_at', 'endedAt', 'ended_at', 
    'duration', 'createdAt', 'created_at', 'updatedAt', 'updated_at'
  ];

  for (const field of disallowedFields) {
    if (body[field] !== undefined) {
      return { isValid: false, error: `Field '${field}' cannot be modified` };
    }
  }

  const { score, performance, notes } = body;

  // At least one valid field must be provided
  if (score === undefined && performance === undefined && notes === undefined) {
    return { 
      isValid: false, 
      error: 'At least one field (score, performance, notes) must be provided for update' 
    };
  }

  if (score !== undefined && score !== null) {
    const numScore = Number(score);
    if (isNaN(numScore) || !isFinite(numScore)) {
      return { isValid: false, error: 'Score must be a valid numeric value' };
    }
  }

  if (performance !== undefined && performance !== null) {
    if (typeof performance !== 'string') {
      return { isValid: false, error: 'Performance must be a string' };
    }
    if (performance.trim().length > 255) {
      return { isValid: false, error: 'Performance must not exceed 255 characters' };
    }
  }

  if (notes !== undefined && notes !== null) {
    if (typeof notes !== 'string') {
      return { isValid: false, error: 'Notes must be a string' };
    }
    if (notes.trim().length > 5000) {
      return { isValid: false, error: 'Notes must not exceed 5000 characters' };
    }
  }

  return { isValid: true };
};

/**
 * Validate memory creation payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateCreateMemoryInput = ({ title, summary, memoryType, sessionId, metadata }) => {
  if (!title || typeof title !== 'string' || title.trim().length === 0) {
    return { isValid: false, error: 'Title is required' };
  }

  if (title.trim().length > 255) {
    return { isValid: false, error: 'Title must not exceed 255 characters' };
  }

  if (!memoryType || typeof memoryType !== 'string' || memoryType.trim().length === 0) {
    return { isValid: false, error: 'memoryType is required' };
  }

  if (memoryType.trim().length > 100) {
    return { isValid: false, error: 'memoryType must not exceed 100 characters' };
  }

  if (summary !== undefined && summary !== null) {
    if (typeof summary !== 'string') {
      return { isValid: false, error: 'Summary must be a string' };
    }
    if (summary.trim().length > 5000) {
      return { isValid: false, error: 'Summary must not exceed 5000 characters' };
    }
  }

  if (sessionId !== undefined && sessionId !== null) {
    if (typeof sessionId !== 'string' || !isValidUUID(sessionId)) {
      return { isValid: false, error: 'Valid sessionId (UUID) is required' };
    }
  }

  if (metadata !== undefined) {
    if (!isValidMetadata(metadata)) {
      return { isValid: false, error: 'Metadata must be a valid JSON object' };
    }
  }

  return { isValid: true };
};

/**
 * Validate memory update payload
 * @param {Object} body 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateUpdateMemoryInput = (body) => {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { isValid: false, error: 'Request body must be an object' };
  }

  const disallowedFields = [
    'id', 'userId', 'user_id', 'sessionId', 'session_id', 
    'createdAt', 'created_at', 'updatedAt', 'updated_at'
  ];

  for (const field of disallowedFields) {
    if (body[field] !== undefined) {
      return { isValid: false, error: `Field '${field}' cannot be modified` };
    }
  }

  const { title, summary, memoryType, metadata } = body;

  if (title === undefined && summary === undefined && memoryType === undefined && metadata === undefined) {
    return {
      isValid: false,
      error: 'At least one field (title, summary, memoryType, metadata) must be provided for update'
    };
  }

  if (title !== undefined) {
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return { isValid: false, error: 'Title cannot be empty' };
    }
    if (title.trim().length > 255) {
      return { isValid: false, error: 'Title must not exceed 255 characters' };
    }
  }

  if (memoryType !== undefined) {
    if (!memoryType || typeof memoryType !== 'string' || memoryType.trim().length === 0) {
      return { isValid: false, error: 'memoryType cannot be empty' };
    }
    if (memoryType.trim().length > 100) {
      return { isValid: false, error: 'memoryType must not exceed 100 characters' };
    }
  }

  if (summary !== undefined && summary !== null) {
    if (typeof summary !== 'string') {
      return { isValid: false, error: 'Summary must be a string' };
    }
    if (summary.trim().length > 5000) {
      return { isValid: false, error: 'Summary must not exceed 5000 characters' };
    }
  }

  if (metadata !== undefined) {
    if (!isValidMetadata(metadata)) {
      return { isValid: false, error: 'Metadata must be a valid JSON object' };
    }
  }

  return { isValid: true };
};

/**
 * Validate task creation payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateCreateTaskInput = ({ title, description, priority, dueDate, estimatedMinutes }) => {
  if (!title || typeof title !== 'string' || title.trim().length === 0) {
    return { isValid: false, error: 'Title is required' };
  }

  if (title.trim().length > 255) {
    return { isValid: false, error: 'Title must not exceed 255 characters' };
  }

  if (description !== undefined && description !== null) {
    if (typeof description !== 'string') {
      return { isValid: false, error: 'Description must be a string' };
    }
  }

  if (priority !== undefined && priority !== null) {
    if (typeof priority !== 'string' || !ALLOWED_PRIORITIES.includes(priority.trim().toLowerCase())) {
      return { isValid: false, error: "Priority must be one of: 'low', 'medium', 'high'" };
    }
  }

  if (dueDate !== undefined && dueDate !== null) {
    if (!isValidDate(dueDate)) {
      return { isValid: false, error: 'Invalid due date format: must be a valid ISO date string' };
    }
  }

  if (estimatedMinutes !== undefined && estimatedMinutes !== null) {
    const mins = Number(estimatedMinutes);
    if (!Number.isInteger(mins) || mins <= 0) {
      return { isValid: false, error: 'Estimated minutes must be a positive integer greater than 0' };
    }
  }

  return { isValid: true };
};

/**
 * Validate task update payload
 * @param {Object} body 
 * @returns {{ isValid: boolean, error?: string }}
 */
const validateUpdateTaskInput = (body) => {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { isValid: false, error: 'Request body must be an object' };
  }

  const disallowedFields = [
    'id', 'userId', 'user_id', 'createdAt', 'created_at', 'updatedAt', 'updated_at'
  ];

  for (const field of disallowedFields) {
    if (body[field] !== undefined) {
      return { isValid: false, error: `Field '${field}' cannot be modified` };
    }
  }

  const { title, description, priority, dueDate, estimatedMinutes, completed } = body;

  if (
    title === undefined &&
    description === undefined &&
    priority === undefined &&
    dueDate === undefined &&
    estimatedMinutes === undefined &&
    completed === undefined
  ) {
    return {
      isValid: false,
      error: 'At least one field (title, description, priority, dueDate, estimatedMinutes, completed) must be provided for update'
    };
  }

  if (title !== undefined) {
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return { isValid: false, error: 'Title cannot be empty' };
    }
    if (title.trim().length > 255) {
      return { isValid: false, error: 'Title must not exceed 255 characters' };
    }
  }

  if (description !== undefined && description !== null) {
    if (typeof description !== 'string') {
      return { isValid: false, error: 'Description must be a string' };
    }
  }

  if (priority !== undefined && priority !== null) {
    if (typeof priority !== 'string' || !ALLOWED_PRIORITIES.includes(priority.trim().toLowerCase())) {
      return { isValid: false, error: "Priority must be one of: 'low', 'medium', 'high'" };
    }
  }

  if (dueDate !== undefined && dueDate !== null) {
    if (!isValidDate(dueDate)) {
      return { isValid: false, error: 'Invalid due date format: must be a valid ISO date string' };
    }
  }

  if (estimatedMinutes !== undefined && estimatedMinutes !== null) {
    const mins = Number(estimatedMinutes);
    if (!Number.isInteger(mins) || mins <= 0) {
      return { isValid: false, error: 'Estimated minutes must be a positive integer greater than 0' };
    }
  }

  if (completed !== undefined) {
    if (typeof completed !== 'boolean') {
      return { isValid: false, error: 'Completed must be a boolean value' };
    }
  }

  return { isValid: true };
};

/**
 * Validate pagination parameters
 * @param {Object} query 
 * @returns {{ isValid: boolean, page: number, limit: number, error?: string }}
 */
const validatePagination = (query = {}) => {
  let page = 1;
  let limit = 20;

  if (query.page !== undefined) {
    const parsedPage = parseInt(query.page, 10);
    if (isNaN(parsedPage) || parsedPage < 1 || String(parsedPage) !== String(query.page).trim()) {
      return { isValid: false, page: 1, limit: 20, error: 'Invalid page parameter: must be a positive integer >= 1' };
    }
    page = parsedPage;
  }

  if (query.limit !== undefined) {
    const parsedLimit = parseInt(query.limit, 10);
    if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 100 || String(parsedLimit) !== String(query.limit).trim()) {
      return { isValid: false, page: 1, limit: 20, error: 'Invalid limit parameter: must be an integer between 1 and 100' };
    }
    limit = parsedLimit;
  }

  return { isValid: true, page, limit };
};

/**
 * Validate task filter query parameters (pagination + completed + priority)
 * @param {Object} query 
 * @returns {{ isValid: boolean, page?: number, limit?: number, completed?: boolean, priority?: string, error?: string }}
 */
const validateTaskFilterQuery = (query = {}) => {
  const paginationResult = validatePagination(query);
  if (!paginationResult.isValid) {
    return paginationResult;
  }

  let completedFilter = undefined;
  if (query.completed !== undefined) {
    const val = String(query.completed).trim().toLowerCase();
    if (val === 'true') {
      completedFilter = true;
    } else if (val === 'false') {
      completedFilter = false;
    } else {
      return { isValid: false, error: "Invalid completed parameter: must be 'true' or 'false'" };
    }
  }

  let priorityFilter = undefined;
  if (query.priority !== undefined) {
    const val = String(query.priority).trim().toLowerCase();
    if (!ALLOWED_PRIORITIES.includes(val)) {
      return { isValid: false, error: "Invalid priority parameter: must be 'low', 'medium', or 'high'" };
    }
    priorityFilter = val;
  }

  return {
    isValid: true,
    page: paginationResult.page,
    limit: paginationResult.limit,
    completed: completedFilter,
    priority: priorityFilter
  };
};

/**
 * Validate AI chat input payload
 * @param {Object} param0 
 * @returns {{ isValid: boolean, message?: string, error?: string }}
 */
const validateAiChatInput = ({ message } = {}) => {
  if (message === undefined || message === null) {
    return { isValid: false, error: 'Message is required' };
  }

  if (typeof message !== 'string') {
    return { isValid: false, error: 'Message must be a string' };
  }

  const trimmed = message.trim();
  if (trimmed.length === 0) {
    return { isValid: false, error: 'Message is required' };
  }

  if (trimmed.length > 2000) {
    return { isValid: false, error: 'Message must not exceed 2000 characters' };
  }

  return { isValid: true, message: trimmed };
};

module.exports = {
  isValidEmail,
  normalizeEmail,
  isValidUUID,
  isValidMetadata,
  isValidDate,
  validateSignupInput,
  validateLoginInput,
  validateGameInput,
  validateCreateSessionInput,
  validateUpdateSessionInput,
  validateCreateMemoryInput,
  validateUpdateMemoryInput,
  validateCreateTaskInput,
  validateUpdateTaskInput,
  validatePagination,
  validateTaskFilterQuery,
  validateAiChatInput,
  ALLOWED_PRIORITIES,
  MIN_PASSWORD_LENGTH
};
