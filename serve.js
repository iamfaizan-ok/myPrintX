const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const USER_FRONTEND_DIR = path.join(__dirname, 'user_frontend');
const ADMIN_DIR = path.join(__dirname, 'admin');

const MIME_TYPES = {
  '.html': 'text/html; charset=UTF-8',
  '.css': 'text/css; charset=UTF-8',
  '.js': 'application/javascript; charset=UTF-8',
  '.json': 'application/json; charset=UTF-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.pdf': 'application/pdf',
  '.ico': 'image/x-icon'
};

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  let reqPath = decodeURI(req.url.split('?')[0]);

  let rootDir = USER_FRONTEND_DIR;
  let relativePath = reqPath;

  if (reqPath.startsWith('/admin')) {
    rootDir = ADMIN_DIR;
    relativePath = reqPath.slice('/admin'.length);
    if (relativePath === '' || relativePath === '/') {
      relativePath = '/index.html';
    }
  } else {
    if (relativePath === '' || relativePath === '/') {
      relativePath = '/index.html';
    }
  }

  const filePath = path.join(rootDir, relativePath);

  if (!filePath.startsWith(rootDir)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('403 Forbidden');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end(`404 Not Found: ${reqPath}`);
      return;
    }

    if (stats.isDirectory()) {
      const target = reqPath.endsWith('/') ? reqPath + 'index.html' : reqPath + '/index.html';
      res.writeHead(302, { Location: target });
      res.end();
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    res.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': stats.size,
      'Cache-Control': 'no-cache'
    });
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(PORT, () => {
  console.log(`PrintX Frontend & Admin Hub running at http://localhost:${PORT}`);
});
