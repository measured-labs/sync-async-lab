const http = require('http');
const express = require('express');
const { Pool } = require('pg');
const { WebSocketServer } = require('ws');

const app = express();
const server = http.createServer(app);

const dbHost = process.env.DB_HOST || 'postgres';
const pool = new Pool({
  host: dbHost, port: 5432, database: 'bench', user: 'bench', password: 'bench',
  max: 20, min: 5,
});

function fibonacci(n) {
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2);
}

app.get('/io', async (req, res) => {
  await new Promise(resolve => setTimeout(resolve, 200));
  res.json({ server: 'node-express', type: 'io', delay_ms: 200 });
});

app.get('/cpu', (req, res) => {
  const result = fibonacci(38);
  res.json({ server: 'node-express', type: 'cpu', fibonacci: result });
});

app.get('/db', async (req, res) => {
  await pool.query('SELECT pg_sleep(0.2)');
  res.json({ server: 'node-express', type: 'db', delay_ms: 200 });
});

const wss = new WebSocketServer({ server, path: '/ws' });
wss.on('connection', (ws) => {
  ws.on('message', (data) => {
    ws.send(data.toString());
  });
});

server.listen(8080, () => {
  console.log('Node.js server listening on :8080');
});
