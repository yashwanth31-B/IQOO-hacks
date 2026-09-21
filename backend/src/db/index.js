const { Pool } = require('pg');
const dotenv = require('dotenv');

const path = require('path');
dotenv.config({ path: path.resolve(__dirname, '../../.env') });
dotenv.config();

const connectionString = process.env.DATABASE_URL;

// Support SSL in production or when connecting to cloud databases (Render, Neon, Supabase, etc.)
const shouldUseSSL =
  process.env.NODE_ENV === 'production' ||
  (connectionString && (connectionString.includes('render.com') || connectionString.includes('sslmode=require')));

const pool = new Pool({
  connectionString: connectionString || 'postgresql://postgres:postgres@localhost:5432/ai_gaming_copilot',
  ssl: shouldUseSSL ? { rejectUnauthorized: false } : false
});

pool.on('error', (err) => {
  console.error('Unexpected error on idle PostgreSQL client:', err);
});

/**
 * Execute a query with parameters using a pool client
 * @param {string} text 
 * @param {Array} params 
 * @returns {Promise<import('pg').QueryResult>}
 */
const query = (text, params) => pool.query(text, params);

/**
 * Acquire a client from the connection pool (useful for transactions)
 * @returns {Promise<import('pg').PoolClient>}
 */
const getClient = () => pool.connect();

/**
 * Test connectivity to the database
 * @returns {Promise<boolean>}
 */
const testConnection = async () => {
  try {
    const res = await pool.query('SELECT 1 AS connected');
    return res.rows && res.rows.length > 0 && res.rows[0].connected === 1;
  } catch (error) {
    console.error('PostgreSQL connection check failed:', error.message);
    return false;
  }
};

module.exports = {
  pool,
  query,
  getClient,
  testConnection
};
