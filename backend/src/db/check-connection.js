const dotenv = require('dotenv');
const { pool, testConnection } = require('./index');

dotenv.config();

async function checkDatabase() {
  console.log('Testing PostgreSQL connection...');
  try {
    const isConnected = await testConnection();
    if (isConnected) {
      const res = await pool.query('SELECT current_database(), current_user, version()');
      console.log('PostgreSQL Connection: SUCCESS');
      console.log(`Database: ${res.rows[0].current_database}`);
      console.log(`User: ${res.rows[0].current_user}`);
      console.log(`PostgreSQL Version: ${res.rows[0].version}`);
    } else {
      console.error('PostgreSQL Connection: FAILED');
      process.exitCode = 1;
    }
  } catch (error) {
    console.error('Error testing PostgreSQL connection:', error.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

if (require.main === module) {
  checkDatabase();
}

module.exports = {
  checkDatabase
};
