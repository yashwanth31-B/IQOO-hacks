const express = require('express');
const taskController = require('../controllers/task.controller');
const { requireAuth } = require('../middleware/auth.middleware');

const router = express.Router();

// Require authentication for ALL task routes
router.use(requireAuth);

// 1. Create task
router.post('/', taskController.createTask);

// 2. Get tasks (paginated with optional filtering)
router.get('/', taskController.getTasks);

// 3. Mark task as completed
router.patch('/:id/complete', taskController.completeTask);

// 4. Mark task as incomplete
router.patch('/:id/incomplete', taskController.incompleteTask);

// 5. Get single task by ID
router.get('/:id', taskController.getTaskById);

// 6. Update task by ID
router.patch('/:id', taskController.updateTask);

// 7. Delete task by ID
router.delete('/:id', taskController.deleteTask);

module.exports = router;
