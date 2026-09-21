const express = require('express');
const sessionController = require('../controllers/session.controller');
const { requireAuth } = require('../middleware/auth.middleware');

const router = express.Router();

// Require authentication for ALL session routes
router.use(requireAuth);

// 1. Create session
router.post('/', sessionController.createSession);

// 2. Get user's sessions (paginated)
router.get('/', sessionController.getUserSessions);

// 3. Get currently active session (placed before /:id to prevent route collision)
router.get('/active', sessionController.getActiveSession);

// 4. Get single session by ID
router.get('/:id', sessionController.getSessionById);

// 5. Update session by ID
router.patch('/:id', sessionController.updateSession);

// 6. End active session by ID
router.post('/:id/end', sessionController.endSession);

// 7. Delete session by ID
router.delete('/:id', sessionController.deleteSession);

module.exports = router;
