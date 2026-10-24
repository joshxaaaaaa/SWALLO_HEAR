// Forwards /api/* from the Expo dev server to the SWALLOHear analysis server (api/server.py) on the same computer.
// The phone then reaches the analysis through the same address and port it loaded the app from, so it works on
// any Wi-Fi or hotspot (and through `expo start --tunnel`) without configuring a server address.
const http = require('http');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
const API = new URL(process.env.SWALLOHEAR_API || 'http://127.0.0.1:8000');

function proxy(req, res) {
  const upstream = http.request(
    { hostname: API.hostname, port: API.port, path: req.url, method: req.method, headers: { ...req.headers, host: API.host } },
    (r) => { res.writeHead(r.statusCode || 502, r.headers); r.pipe(res); },
  );
  upstream.on('error', (e) => {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: `The analysis server is not running on this computer (${e.code}). Start it with "python api/server.py".` }));
  });
  req.pipe(upstream);
}

const previous = config.server.enhanceMiddleware;
config.server.enhanceMiddleware = (middleware, server) => {
  const next = previous ? previous(middleware, server) : middleware;
  return (req, res, cont) => (req.url && req.url.startsWith('/api/') ? proxy(req, res) : next(req, res, cont));
};

module.exports = config;
