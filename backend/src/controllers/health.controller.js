const { testConnection } = require('../db');

/**
 * Health check controller
 */
const getHealth = async (req, res) => {
  const isDbConnected = await testConnection();

  res.status(200).json({
    success: true,
    message: 'AI Gaming Copilot API is running',
    database: isDbConnected ? 'connected' : 'disconnected'
  });
};

module.exports = {
  getHealth
};
