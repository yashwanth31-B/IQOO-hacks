/**
 * Health check controller
 */
const getHealth = (req, res) => {
  res.status(200).json({
    success: true,
    message: 'AI Gaming Copilot API is running'
  });
};

module.exports = {
  getHealth
};
