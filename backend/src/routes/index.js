const express = require('express');
const healthRoutes = require('./health.routes');
const authRoutes = require('./auth.routes');
const gameRoutes = require('./game.routes');
const sessionRoutes = require('./session.routes');
const memoryRoutes = require('./memory.routes');

const router = express.Router();

// Mount route modules
router.use('/', healthRoutes);
router.use('/auth', authRoutes);
router.use('/games', gameRoutes);
router.use('/sessions', sessionRoutes);
router.use('/memories', memoryRoutes);

module.exports = router;
