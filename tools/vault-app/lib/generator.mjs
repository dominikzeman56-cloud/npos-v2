// Místní generátor presetů: tenká obálka kolem tools/preset_seed.py. Běží jen v živém serveru (node server.mjs, vazba na 127.0.0.1),
// nikdy ve statickém exportu. Nic neposílá ven: soubory vznikají ve složce z NPOS_SERUM_OUT na počítači, kde server běží, a odpověď
// obsahuje jen jména a počty. Odvozené presety patří k tvým vlastním packům, nesdílej je.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROLES = ['bass', 'reese', 'neuro', 'sub', 'stab', 'lead', 'pluck', 'chords', 'pad', 'seq', 'synth', 'layer', 'guitar', 'perc', 'fx', 'other'];

// Volitelný soubor .env.local vedle server.mjs (je v .gitignore): řádky KLÍČ=hodnota, jen klíče NPOS_* a VAULT_PATH.
export function loadEnvFile(file, env = process.env) {
  let txt = '';
  try { txt = fs.readFileSync(file, 'utf8'); } catch { return 0; }
  let n = 0;
  for (const line of txt.split(/\r?\n/)) {
    const m = /^\s*((?:NPOS_[A-Z_]+)|VAULT_PATH)\s*=\s*(.*?)\s*$/.exec(line);
    if (m && env[m[1]] === undefined) { env[m[1]] = m[2].replace(/^"(.*)"$/, '$1'); n++; }
  }
  return n;
}

export function genConfig(repo, env = process.env) {
  const roots = (env.NPOS_SERUM_PRESETS || '').split(path.delimiter).map((s) => s.trim()).filter(Boolean);
  const py = (env.NPOS_PYTHON || (process.platform === 'win32' ? 'py -3.12' : 'python3')).split(/\s+/).filter(Boolean);
  return { roots, out: env.NPOS_SERUM_OUT || '', cmd: py[0], cmdArgs: py.slice(1), script: path.join(repo, 'tools', 'preset_seed.py'), repo };
}

// Obrana proti cizím stránkám v prohlížeči: musí sedět Host i Origin (DNS rebinding, formuláře z jiných webů) a vlastní hlavička.
export function guard(req, port) {
  const ok = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
  if (!ok.has(String(req.headers.host || '').toLowerCase())) return 'Host není lokální';
  const o = req.headers.origin;
  if (o && ![`http://127.0.0.1:${port}`, `http://localhost:${port}`].includes(o)) return 'Origin není lokální';
  if (req.method === 'POST') {
    if (req.headers['x-npos'] !== '1') return 'chybí hlavička X-NPOS';
    if (!String(req.headers['content-type'] || '').startsWith('application/json')) return 'očekává se application/json';
  }
  return null;
}

const int = (v, lo, hi, d) => { const n = v === undefined || v === null ? d : Number(v); return Number.isInteger(n) && n >= lo && n <= hi ? n : null; };
export function validate(b) {
  if (!b || typeof b !== 'object') return { error: 'tělo musí být JSON objekt' };
  const role = b.role === undefined ? undefined : String(b.role);
  if (role !== undefined && !ROLES.includes(role)) return { error: 'neznámá role' };
  const fromId = b.fromId === undefined || b.fromId === '' ? undefined : String(b.fromId);
  if (fromId !== undefined && !/^[A-Za-z0-9._-]{1,200}$/.test(fromId)) return { error: 'neplatné id semínka' };
  if (!role && !fromId) return { error: 'zadej roli nebo id semínka' };
  const n = int(b.n, 1, 8, 3), mutate = int(b.mutate, 1, 8, 4), seed = int(b.seed, 0, 1_000_000, 1);
  const spread = b.spread === undefined ? 0.25 : Number(b.spread);
  if (n === null || mutate === null || seed === null) return { error: 'n a mutate 1–8, seed 0–1000000' };
  if (!(spread >= 0.05 && spread <= 0.8)) return { error: 'spread 0,05–0,8' };
  return { ok: { role, fromId, n, mutate, seed, spread, check: b.check === true } };
}

export function buildArgs(cfg, v, extra = []) {
  const args = ['--roots', ...cfg.roots];
  if (v) {
    if (v.role) args.push('--role', v.role);
    if (v.fromId) args.push('--from-id', v.fromId);
    args.push('--n', String(v.n), '--mutate', String(v.mutate), '--seed', String(v.seed), '--spread', String(v.spread), '--out', cfg.out, '--json');
    if (v.check) args.push('--check');
  }
  return [...args, ...extra];
}

let busy = false;
export const isBusy = () => busy;

// Spustí skript bez shellu; `args` jsou jen naše ověřené hodnoty. Vrací { code, stdout, stderr }.
export function run(cfg, args, { timeoutMs = 300_000 } = {}) {
  return new Promise((resolve) => {
    const p = spawn(cfg.cmd, [...cfg.cmdArgs, '-X', 'utf8', cfg.script, ...args], { cwd: cfg.repo, shell: false, windowsHide: true });
    let out = '', err = '';
    const t = setTimeout(() => { err += '\npřekročen časový limit'; p.kill(); }, timeoutMs);
    p.stdout.on('data', (d) => { out += d; if (out.length > 200_000) out = out.slice(-200_000); });
    p.stderr.on('data', (d) => { err += d; if (err.length > 20_000) err = err.slice(-20_000); });
    p.on('error', (e) => { clearTimeout(t); resolve({ code: -1, stdout: out, stderr: String(e.message) }); });
    p.on('close', (code) => { clearTimeout(t); resolve({ code, stdout: out, stderr: err }); });
  });
}

export async function status(cfg) {
  const configured = cfg.roots.length > 0 && !!cfg.out;
  const base = { configured, roots: cfg.roots, out: cfg.out, roles: {}, ready: false, note: '' };
  if (!configured) return { ...base, note: 'Nastav NPOS_SERUM_PRESETS (složky s Serum 2 presety) a NPOS_SERUM_OUT (kam se uloží výsledek), nejlépe v tools/vault-app/.env.local.' };
  for (const r of cfg.roots) if (!fs.existsSync(r)) return { ...base, note: 'Složka s presety neexistuje: ' + r };
  const r = await run(cfg, buildArgs(cfg, null, ['--list-roles']), { timeoutMs: 120_000 });
  if (r.code !== 0) return { ...base, note: 'Python nebo skript selhal: ' + (r.stderr.trim().split('\n').pop() || 'kód ' + r.code) };
  try { return { ...base, roles: JSON.parse(r.stdout.trim().split('\n').pop()), ready: true }; } catch { return { ...base, note: 'Neočekávaný výstup skriptu' }; }
}

export async function generate(cfg, v) {
  if (busy) return { status: 409, body: { error: 'generování už běží' } };
  busy = true;
  try {
    const r = await run(cfg, buildArgs(cfg, v), { timeoutMs: v.check ? 900_000 : 300_000 });
    let summary = null;
    try { summary = JSON.parse(r.stdout.trim().split('\n').filter((l) => l.startsWith('{')).pop()); } catch { /* bez souhrnu */ }
    const msg = r.stderr.trim().split('\n').slice(-3).join(' | ');
    if (!summary) return { status: 500, body: { error: msg || 'skript nevrátil výsledek', code: r.code } };
    return { status: 200, body: { ...summary, code: r.code, message: r.code === 0 ? '' : msg } };
  } finally { busy = false; }
}
