const express = require('express');
const memoryController = require('../controllers/memory.controller');
const { requireAuth } = require('../middleware/auth.middleware');

const router = express.Router();

// Require authentication for ALL memory routes
router.use(requireAuth);

// 1. Create memory
router.post('/', memoryController.createMemory);

// 2. Get memories (paginated with optional filtering)
router.get('/', memoryController.getMemories);

// 3. Get single memory by ID
router.get('/:id', memoryController.getMemoryById);

// 4. Update memory by ID
router.patch('/:id', memoryController.updateMemory);

// 5. Delete memory by ID
router.delete('/:id', memoryController.deleteMemory);

module.exports = router;
