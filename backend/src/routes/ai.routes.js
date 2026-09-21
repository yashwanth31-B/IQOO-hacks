const express = require('express');
const aiController = require('../controllers/ai.controller');
const { requireAuth } = require('../middleware/auth.middleware');

const router = express.Router();

// Require authentication for all AI routes
router.use(requireAuth);

// POST /api/ai/chat
router.post('/chat', aiController.chat);

module.exports = router;
