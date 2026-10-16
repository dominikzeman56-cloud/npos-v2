// Integration tests for the live server (server.mjs): starts it on a throwaway port against a temporary vault.
// Run: npm test (node --test). No network, no real vault needed.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = 47000 + Math.floor(Math.random() * 1000);
const BASE = `http://127.0.0.1:${PORT}`;
let proc, vault;

async function waitUp() {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`${BASE}/api/index`); if (r.ok) return; } catch { /* not yet */ }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error('server did not start');
}

before(async () => {
  vault = await fs.mkdtemp(path.join(os.tmpdir(), 'vault-test-'));
  await fs.mkdir(path.join(vault, 'Sekce'));
  await fs.writeFile(path.join(vault, '00 Start.md'), '---\ntags: [start]\n---\n# 00 Start\n\nOdkaz na [[20 Basa]] a #rozcestnik.\n');
  await fs.writeFile(path.join(vault, 'Sekce', '20 Basa.md'), '# 20 Basa\n\nReese a sub. Zpět na [[00 Start]].\n');
  await fs.mkdir(path.join(vault, 'tajne'));
  await fs.writeFile(path.join(vault, 'tajne', 'x.md'), '# tajné\n');
  proc = spawn(process.execPath, ['server.mjs'], {
    cwd: HERE, env: { ...process.env, VAULT_PATH: vault, PORT: String(PORT), VAULT_IGNORE: 'tajne,.obsidian', NPOS_SERUM_PRESETS: '', NPOS_SERUM_OUT: '' }, stdio: 'ignore',
  });
  await waitUp();
});

after(async () => {
  proc?.kill();
  if (vault) await fs.rm(vault, { recursive: true, force: true });
});

const get = (p) => fetch(BASE + p);

test('GET /api/index lists the notes of the vault and honors VAULT_IGNORE', async () => {
  const j = await (await get('/api/index')).json();
  const text = JSON.stringify(j);
  assert.ok(text.includes('00 Start'));
  assert.ok(text.includes('20 Basa'));
  assert.ok(!text.includes('tajne'), 'ignored folder must not appear');
});

test('GET /api/note returns a note with backlinks, 404 for an unknown path', async () => {
  const ok = await get('/api/note?path=' + encodeURIComponent('Sekce/20 Basa.md'));
  assert.equal(ok.status, 200);
  const n = await ok.json();
  assert.equal(n.name, '20 Basa');
  assert.ok(Array.isArray(n.backlinks));
  const missing = await get('/api/note?path=neexistuje.md');
  assert.equal(missing.status, 404);
});

test('GET /api/search finds text, /api/tags and /api/graph answer with JSON', async () => {
  const s = await (await get('/api/search?q=reese')).json();
  assert.ok(s.total >= 1);
  assert.ok(Array.isArray(s.results));
  assert.equal((await get('/api/tags')).status, 200);
  const g = await (await get('/api/graph')).json();
  assert.ok(g.nodes.length >= 2 && g.links.length >= 1);
});

test('GET /api/next-step serves the Co dál? decision tree', async () => {
  const r = await get('/api/next-step');
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.ok(d.phases.length > 0 && d.items.length > 0);
  assert.ok(d.items.every((i) => i.steps?.length && i.confidence));
});

test('GET /api/presets returns the compact index, /api/preset validates the id', async () => {
  const p = await (await get('/api/presets')).json();
  assert.ok(Array.isArray(p.presets) && p.presets.length > 0);
  assert.equal((await get('/api/preset?id=..%2F..%2Fetc')).status, 404);
  assert.equal((await get('/api/preset?id=neexistuje-xyz')).status, 404);
});

test('GET /api/presets/similar returns neighbours for a known preset and validates input', async () => {
  const id = (await (await get('/api/presets')).json()).presets[0].id;
  const r = await get(`/api/presets/similar?id=${encodeURIComponent(id)}&k=3`);
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.equal(d.mode, 'params');
  assert.match(d.note, /ne poslech/);
  assert.ok(d.similar.length > 0 && d.similar.length <= 3);
  assert.ok(d.similar.every((x) => x.id !== id && Number.isFinite(x.d) && x.n >= 8));
  assert.equal((await get('/api/presets/similar?id=neexistuje-xyz')).status, 404);
  assert.equal((await get(`/api/presets/similar?id=${encodeURIComponent(id)}&mode=wav`)).status, 400);
});

test('path traversal is refused for static files and /asset', async () => {
  assert.equal((await get('/asset?path=' + encodeURIComponent('../secret.txt'))).status, 403);
  assert.equal((await get('/asset?path=' + encodeURIComponent('tajne/x.md'))).status, 403);
  const r = await fetch(`${BASE}/..%2F..%2Fpackage.json`);
  assert.ok([403, 404].includes(r.status));
});

test('static pages are served', async () => {
  for (const p of ['/', '/dashboard.html', '/presets.html', '/dal.html', '/topbar.js', '/trenazer.html', '/trainer-worklet.js']) {
    const r = await get(p);
    assert.equal(r.status, 200, p);
  }
});

// ── místní generátor presetů: obrana proti cizím stránkám a špatným vstupům (bez Pythonu a bez presetů) ──
const rawReq = (opts, body) => new Promise((resolve, reject) => {
  const r = http.request({ host: '127.0.0.1', port: PORT, ...opts }, (res) => { let t = ''; res.on('data', (d) => { t += d; }); res.on('end', () => resolve({ status: res.statusCode, body: t })); });
  r.on('error', reject); if (body) r.write(body); r.end();
});
const post = (body, headers = {}) => rawReq({ path: '/api/generator/run', method: 'POST', headers: { Host: `127.0.0.1:${PORT}`, 'Content-Type': 'application/json', 'X-NPOS': '1', ...headers } }, JSON.stringify(body));

test('generator status says it is not configured when no folders are set', async () => {
  const r = await rawReq({ path: '/api/generator/status', headers: { 'X-NPOS': '1' } });
  assert.equal(r.status, 200);
  const j = JSON.parse(r.body);
  assert.equal(j.configured, false); assert.equal(j.ready, false);
});

test('generator refuses foreign Host and Origin and a POST without the custom header or JSON type', async () => {
  assert.equal((await rawReq({ path: '/api/generator/status', headers: { Host: 'evil.example:' + PORT } })).status, 403);
  assert.equal((await post({ role: 'bass' }, { Origin: 'https://evil.example' })).status, 403);
  assert.equal((await post({ role: 'bass' }, { 'X-NPOS': '0' })).status, 403);
  assert.equal((await post({ role: 'bass' }, { 'Content-Type': 'text/plain' })).status, 403);
});

test('generator validates input before anything runs: unknown role, bad id, out-of-range numbers, empty body', async () => {
  for (const b of [{ role: 'rm -rf' }, { role: 'bass', fromId: '../x' }, { role: 'bass', n: 99 }, { role: 'bass', spread: 5 }, { role: 'bass', seed: -1 }, {}]) {
    assert.equal((await post(b)).status, 400, JSON.stringify(b));
  }
  assert.equal((await post({ role: 'bass', n: 2 })).status, 412);      // validní, ale generátor není nastavený
});

test('generator pages are served by the local server', async () => {
  for (const p of ['/generator.html', '/generator.js']) assert.equal((await get(p)).status, 200, p);
});
