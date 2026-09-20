const { pool } = require('./index');

async function inspectSchema() {
  try {
    console.log('--- TABLES IN PUBLIC SCHEMA ---');
    const tables = await pool.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      ORDER BY table_name;
    `);
    console.table(tables.rows);

    console.log('--- FOREIGN KEYS ---');
    const fks = await pool.query(`
      SELECT
        tc.table_name, 
        kcu.column_name, 
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name,
        rc.delete_rule
      FROM information_schema.table_constraints AS tc 
      JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
      JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
      JOIN information_schema.referential_constraints AS rc
        ON rc.constraint_name = tc.constraint_name
      WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
      ORDER BY tc.table_name, kcu.column_name;
    `);
    console.table(fks.rows);

    console.log('--- INDEXES ---');
    const indexes = await pool.query(`
      SELECT tablename, indexname, indexdef
      FROM pg_indexes
      WHERE schemaname = 'public'
      ORDER BY tablename, indexname;
    `);
    console.table(indexes.rows.map(r => ({ table: r.tablename, index: r.indexname })));

  } catch (error) {
    console.error('Schema inspection failed:', error);
  } finally {
    await pool.end();
  }
}

inspectSchema();
