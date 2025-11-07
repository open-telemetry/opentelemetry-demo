const mysql = require('mysql2/promise');
const logger = require('pino')();

// Create connection pool
const pool = mysql.createPool({
  host: process.env.MYSQL_HOST || 'mysql',
  port: parseInt(process.env.MYSQL_PORT || '3306'),
  user: process.env.MYSQL_USER || 'quotes_user',
  password: process.env.MYSQL_PASSWORD || 'quotes_password',
  database: process.env.MYSQL_DATABASE || 'quotes',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  enableKeepAlive: true,
  keepAliveInitialDelay: 0
});

// Test connection on startup
pool.getConnection()
  .then(connection => {
    logger.info('MySQL connection pool established successfully');
    connection.release();
  })
  .catch(err => {
    logger.error({ err }, 'Failed to establish MySQL connection pool');
  });

module.exports = pool;
