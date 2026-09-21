const taskService = require('../services/task.service');
const {
  isValidUUID,
  validateCreateTaskInput,
  validateUpdateTaskInput,
  validateTaskFilterQuery
} = require('../utils/validation.utils');

/**
 * Create a new task
 * POST /api/tasks
 */
const createTask = async (req, res, next) => {
  try {
    const validation = validateCreateTaskInput(req.body || {});
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const { title, description, priority, dueDate, estimatedMinutes } = req.body;

    const task = await taskService.createTask({
      userId: req.user.id,
      title,
      description,
      priority,
      dueDate,
      estimatedMinutes
    });

    return res.status(201).json({
      success: true,
      message: 'Task created successfully',
      task
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Retrieve paginated tasks with optional filtering
 * GET /api/tasks
 */
const getTasks = async (req, res, next) => {
  try {
    const filterValidation = validateTaskFilterQuery(req.query || {});
    if (!filterValidation.isValid) {
      return res.status(400).json({
        success: false,
        message: filterValidation.error
      });
    }

    const { page, limit, completed, priority } = filterValidation;

    const result = await taskService.getTasks({
      userId: req.user.id,
      page,
      limit,
      completed,
      priority
    });

    return res.status(200).json({
      success: true,
      tasks: result.tasks,
      data: result.tasks,
      pagination: result.pagination
    });
  } catch (error) {
    return next(error);
  }
};

/**
 * Retrieve a single task by ID
 * GET /api/tasks/:id
 */
const getTaskById = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid task ID format: must be a valid UUID'
      });
    }

    const task = await taskService.getTaskById({
      taskId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      task
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Update task
 * PATCH /api/tasks/:id
 */
const updateTask = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid task ID format: must be a valid UUID'
      });
    }

    const validation = validateUpdateTaskInput(req.body);
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        message: validation.error
      });
    }

    const task = await taskService.updateTask({
      taskId: id,
      userId: req.user.id,
      updates: req.body
    });

    return res.status(200).json({
      success: true,
      message: 'Task updated successfully',
      task
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Mark a task as completed
 * PATCH /api/tasks/:id/complete
 */
const completeTask = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid task ID format: must be a valid UUID'
      });
    }

    const task = await taskService.setTaskCompletion({
      taskId: id,
      userId: req.user.id,
      completed: true
    });

    return res.status(200).json({
      success: true,
      message: 'Task marked as completed',
      task
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Mark a task as incomplete
 * PATCH /api/tasks/:id/incomplete
 */
const incompleteTask = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid task ID format: must be a valid UUID'
      });
    }

    const task = await taskService.setTaskCompletion({
      taskId: id,
      userId: req.user.id,
      completed: false
    });

    return res.status(200).json({
      success: true,
      message: 'Task marked as incomplete',
      task
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

/**
 * Delete task
 * DELETE /api/tasks/:id
 */
const deleteTask = async (req, res, next) => {
  try {
    const { id } = req.params;

    if (!isValidUUID(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid task ID format: must be a valid UUID'
      });
    }

    await taskService.deleteTask({
      taskId: id,
      userId: req.user.id
    });

    return res.status(200).json({
      success: true,
      message: 'Task deleted successfully'
    });
  } catch (error) {
    if (error.statusCode) {
      return res.status(error.statusCode).json({
        success: false,
        message: error.message
      });
    }
    return next(error);
  }
};

module.exports = {
  createTask,
  getTasks,
  getTaskById,
  updateTask,
  completeTask,
  incompleteTask,
  deleteTask
};
