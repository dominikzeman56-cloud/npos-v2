// Read-only Obsidian-like vault viewer (live mode): indexes the vault in memory, serves a JSON API + static UI.
import http from 'node:http';
import fs from 'node:fs/promises';
import { watch } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildIndex, DEFAULT_IGNORE, indexPayload, notePayload, tagsPayload, graphPayload } from './lib/vault-index.mjs';
import { search } from './public/search-core.js';
import { loadPresets, loadBuild } from './lib/presets-data.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VAULT = path.resolve(process.env.VAULT_PATH || 'D:\\ObsidianVault');
const PORT = Number(process.env.PORT) || 4747;
const IGNORE = new Set((process.env.VAULT_IGNORE || DEFAULT_IGNORE.join(',')).split(','));

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.avif': 'image/avif', '.bmp': 'image/bmp',
  '.pdf': 'application/pdf', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp4': 'video/mp4',
  '.webm': 'video/webm', '.woff2': 'font/woff2', '.md': 'text/plain; charset=utf-8', '.txt': 'text/plain; charset=utf-8',
};
const VENDOR = {
  '/vendor/markdown-it.min.js': 'node_modules/markdown-it/dist/markdown-it.min.js',
  '/vendor/d3.min.js': 'node_modules/d3/dist/d3.min.js',
};

let idx = null;
async function rebuild() {
  idx = await buildIndex({ vault: VAULT, ignore: IGNORE });
  console.log(`[index] ${idx.notes.size} notes, ${idx.rels.length} files, ${idx.tags.size} tags`);
}

const json = (res, data, status = 200) => {
  res.writeHead(status, { 'Content-Type': MIME['.json'], 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
};

async function sendFile(res, abs, extra = {}) {
  try {
    const buf = await fs.readFile(abs);
    res.writeHead(200, { 'Content-Type': MIME[path.extname(abs).toLowerCase()] || 'application/octet-stream', ...extra });
    res.end(buf);
  } catch {
    res.writeHead(404); res.end('Not found');
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    const p = url.pathname;
    const q = url.searchParams;

    if (p === '/api/index') return json(res, indexPayload(idx));
    if (p === '/api/note') {
      const n = idx.notes.get(q.get('path') || '');
      return n ? json(res, notePayload(idx, n)) : json(res, { error: 'not found' }, 404);
    }
    if (p === '/api/search') return json(res, search(idx.notes.values(), q.get('q') || ''));
    if (p === '/api/tags') return json(res, tagsPayload(idx));
    if (p === '/api/graph') return json(res, graphPayload(idx));
    if (p === '/api/next-step') return sendFile(res, path.resolve(HERE, '..', '..', 'knowledge', 'guides', 'next-step.json'), { 'Cache-Control': 'no-store' });
    if (p === '/api/presets') return json(res, await loadPresets(path.resolve(HERE, '..', '..')));
    if (p === '/api/preset') { const b = await loadBuild(path.resolve(HERE, '..', '..'), q.get('id')); return b ? json(res, b) : json(res, { error: 'not found' }, 404); }
    if (p === '/asset') {
      const rel = (q.get('path') || '').replace(/\\/g, '/');
      const abs = path.resolve(VAULT, rel);
      const segs = rel.split('/');
      if (!abs.startsWith(VAULT + path.sep) || segs.some((s) => IGNORE.has(s) || s === '..')) {
        res.writeHead(403); return res.end('Forbidden');
      }
      return sendFile(res, abs, { 'Cache-Control': 'max-age=60' });
    }
    if (VENDOR[p]) return sendFile(res, path.join(HERE, VENDOR[p]), { 'Cache-Control': 'max-age=3600' });

    const rel = p === '/' ? 'index.html' : p.slice(1);
    const abs = path.resolve(HERE, 'public', rel);
    if (!abs.startsWith(path.join(HERE, 'public') + path.sep)) { res.writeHead(403); return res.end('Forbidden'); }
    return sendFile(res, abs, { 'Cache-Control': 'no-store' });
  } catch (err) {
    console.error(err);
    json(res, { error: String(err) }, 500);
  }
});

let timer = null;
function scheduleRebuild(file) {
  if (file && file.split(/[\\/]/).some((s) => IGNORE.has(s))) return;
  clearTimeout(timer);
  timer = setTimeout(() => rebuild().catch(console.error), 600);
}

await rebuild();
try { watch(VAULT, { recursive: true }, (_e, f) => scheduleRebuild(f)); } catch (e) { console.warn('watch failed:', e.message); }
server.listen(PORT, '127.0.0.1', () => console.log(`Vault viewer: http://127.0.0.1:${PORT}  (vault: ${VAULT})`));
