const express = require('express');
const aiController = require('../controllers/ai.controller');
const { requireAuth } = require('../middleware/auth.middleware');

const router = express.Router();

// Require authentication for all AI routes
router.use(requireAuth);

// POST /api/ai/chat
router.post('/chat', aiController.chat);

// Persistent AI Conversation Endpoints
router.post('/conversations', aiController.createConversation);
router.get('/conversations', aiController.listConversations);
router.get('/conversations/:id', aiController.getConversation);
router.delete('/conversations/:id', aiController.deleteConversation);

module.exports = router;
