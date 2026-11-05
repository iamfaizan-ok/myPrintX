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

function serveFile(res, filePath) {
  fs.stat(filePath, (err, stats) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=UTF-8' });
      res.end('404 Not Found');
      return;
    }

    if (stats.isDirectory()) {
      const indexCandidate = path.join(filePath, 'index.html');
      if (fs.existsSync(indexCandidate)) {
        return serveFile(res, indexCandidate);
      }
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=UTF-8' });
      res.end('403 Forbidden: Directory Listing Not Allowed');
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
}

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

  // Normalize /admin trailing slash to preserve relative link resolution
  if (reqPath === '/admin') {
    res.writeHead(302, { Location: '/admin/' });
    res.end();
    return;
  }

  // Handle /admin/pages shortcut
  if (reqPath === '/admin/pages' || reqPath === '/admin/pages/') {
    res.writeHead(302, { Location: '/admin/pages/orders.html' });
    res.end();
    return;
  }

  // Admin routing
  if (reqPath.startsWith('/admin/')) {
    let subPath = reqPath.slice('/admin'.length);
    if (subPath === '' || subPath === '/') {
      subPath = '/index.html';
    }
    const adminFilePath = path.join(ADMIN_DIR, subPath);

    if (!adminFilePath.startsWith(ADMIN_DIR)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=UTF-8' });
      res.end('403 Forbidden');
      return;
    }

    return serveFile(res, adminFilePath);
  }

  // User Frontend routing with automatic Admin asset fallback
  let userRelative = reqPath;
  if (userRelative === '' || userRelative === '/') {
    userRelative = '/index.html';
  }
  const userFilePath = path.join(USER_FRONTEND_DIR, userRelative);

  if (!userFilePath.startsWith(USER_FRONTEND_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=UTF-8' });
    res.end('403 Forbidden');
    return;
  }

  // Check if file exists in user_frontend
  fs.stat(userFilePath, (err, stats) => {
    if (!err && (stats.isFile() || stats.isDirectory())) {
      return serveFile(res, userFilePath);
    }

    // Fallback: Check if file exists in admin/ (e.g., /css/admin.css or /js/auth.js requested from root)
    const adminFallbackPath = path.join(ADMIN_DIR, reqPath);
    if (adminFallbackPath.startsWith(ADMIN_DIR) && fs.existsSync(adminFallbackPath) && fs.statSync(adminFallbackPath).isFile()) {
      return serveFile(res, adminFallbackPath);
    }

    res.writeHead(404, { 'Content-Type': 'text/plain; charset=UTF-8' });
    res.end(`404 Not Found: ${reqPath}`);
  });
});

const os = require('os');

function getLanIp() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return '127.0.0.1';
}

server.listen(PORT, '0.0.0.0', () => {
  const lanIp = getLanIp();
  console.log(`PrintX Frontend & Admin Hub running:`);
  console.log(`  > Local:   http://localhost:${PORT}`);
  console.log(`  > Network: http://${lanIp}:${PORT} (For Mobile Testing on same Wi-Fi)`);
});
