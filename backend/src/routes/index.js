const express = require('express');
const healthRoutes = require('./health.routes');

const router = express.Router();

// Mount route modules
router.use('/', healthRoutes);

module.exports = router;
