// "Podobné presety": vzdálenost nad čísly z data/presets/features/*.jsonl (parametry ze souboru) a volitelně nad
// data/presets/audio/*.jsonl (deskriptory renderu jedné noty E1). Čísla, žádné audio, wav ani jména wavetablů.
// Porovnání parametrů = z-skóre na klíčích, které mají oba presety (S1 má část klíčů null), vzdálenost = RMS rozdílů.
import fs from 'node:fs/promises';
import path from 'node:path';

const readJsonl = async (file) =>
  (await fs.readFile(file, 'utf8')).split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));

async function readDir(dir) {
  let files = [];
  try { files = (await fs.readdir(dir)).filter((f) => f.endsWith('.jsonl')).sort(); } catch { return []; }
  const out = [];
  for (const f of files) { try { out.push(...await readJsonl(path.join(dir, f))); } catch { /* soubor se právě zapisuje */ } }
  return out;
}

// stejný výběr a transformace jako tools/preset_roles.py (FEATURES), 'attack' = okno výřezu je náběh
export const AUDIO_KEYS = [['rms_db'], ['crest_db'], ['band_sub_pct'], ['band_low_pct'], ['band_mid_pct'], ['band_high_pct'], ['band_air_pct'],
  ['centroid_hz', 'log'], ['rolloff85_hz', 'log'], ['harmonic_pct'], ['am_depth', 'log1p'], ['side_minus_mid_db', 'clip'], ['upper_db'],
  ['upper_centroid_hz', 'log'], ['upper_flatness'], ['upper_motion', 'log1p'], ['upper_flux', 'log1p'], ['attack']];
export const MIN_SHARED = { params: 8, audio: 10 };
export const MODES = Object.keys(MIN_SHARED);

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
export function audioVector(a) {
  const out = {};
  for (const [k, tr] of AUDIO_KEYS) {
    let v;
    if (k === 'attack') v = a.window === 'attack' ? 1 : 0;
    else if (!finite(a[k])) continue;
    else if (tr === 'log') v = Math.log10(Math.max(a[k], 1));
    else if (tr === 'log1p') v = Math.log1p(Math.max(a[k], 0));
    else if (tr === 'clip') v = Math.max(a[k], -40);
    else v = a[k];
    out[k] = v;
  }
  return out;
}

// Vektory jako Map<id, {key: number}> + střední hodnota a směrodatná odchylka každého klíče přes celý soubor.
function standardize(vectors) {
  const acc = new Map();
  for (const v of vectors.values()) for (const [k, x] of Object.entries(v)) {
    const a = acc.get(k) || { n: 0, s: 0, q: 0 }; a.n++; a.s += x; a.q += x * x; acc.set(k, a);
  }
  const stat = new Map();
  for (const [k, a] of acc) {
    const m = a.s / a.n, sd = Math.sqrt(Math.max(0, a.q / a.n - m * m));
    if (a.n >= 5 && sd > 1e-9) stat.set(k, { m, sd }); // klíč bez rozptylu nic nerozliší
  }
  const z = new Map();
  for (const [id, v] of vectors) {
    const o = {};
    for (const [k, x] of Object.entries(v)) { const s = stat.get(k); if (s) o[k] = (x - s.m) / s.sd; }
    z.set(id, o);
  }
  return z;
}

function distance(a, b) {
  let n = 0, sum = 0;
  for (const k in a) if (k in b) { const d = a[k] - b[k]; sum += d * d; n++; }
  return { n, d: n ? Math.sqrt(sum / n) : Infinity };
}

export async function loadPool(repoRoot) {
  const root = path.join(repoRoot, 'data', 'presets');
  const [index, fxp, features, audio, sources] = await Promise.all([
    readDir(path.join(root, 'index')), readDir(path.join(root, 'fxp')), readDir(path.join(root, 'features')),
    readDir(path.join(root, 'audio')),
    readJsonl(path.join(repoRoot, 'knowledge', 'sources.jsonl')).catch(() => []),
  ]);
  const title = new Map(sources.map((s) => [s.id, s.title || s.id]));
  const meta = new Map();
  for (const r of [...fxp, ...index]) {
    meta.set(r.id, { id: r.id, name: r.name, source_id: r.source_id, pack: title.get(r.source_id) || r.source_id, role: r.role, synth: r.synth });
  }
  const params = new Map();
  for (const r of features) {
    if (!meta.has(r.id)) continue; // feature bez řádku v index/ nebo fxp/ nemá jméno
    const v = {};
    for (const [k, x] of Object.entries(r.features || {})) if (finite(x)) v[k] = x;
    params.set(r.id, v);
  }
  const snd = new Map();
  for (const r of audio) {
    if (!meta.has(r.id) || !r.audio || r.audio.silent) continue;
    if (!snd.has(r.id)) snd.set(r.id, audioVector(r.audio));
  }
  return { meta, vectors: { params: standardize(params), audio: standardize(snd) } };
}

// k nejbližších presetů pro `id`; null = neznámé id nebo žádná data v tomto režimu
export function similar(pool, id, { mode = 'params', k = 8 } = {}) {
  if (!MODES.includes(mode)) return null;
  const vecs = pool.vectors[mode];
  const q = vecs.get(id);
  if (!q) return null;
  const out = [];
  for (const [oid, v] of vecs) {
    if (oid === id) continue;
    const { n, d } = distance(q, v);
    if (n >= MIN_SHARED[mode]) out.push({ id: oid, d, n });
  }
  out.sort((a, b) => a.d - b.d || (a.id < b.id ? -1 : 1));
  return out.slice(0, Math.max(1, Math.min(k, 30))).map(({ id: oid, d, n }) => {
    const m = pool.meta.get(oid);
    return { id: oid, name: m.name, pack: m.pack, source_id: m.source_id, role: m.role, d: Math.round(d * 1000) / 1000, n };
  });
}

// Statický export: sousedi předpočítaní pro dané id (ta, která prohlížeč zobrazuje).
export function similarAll(pool, ids, k = 8) {
  const out = { note: 'podobnost parametrů/zvuku z jedné noty, ne poslech', packs: {}, params: {}, audio: {} };
  for (const id of ids) for (const mode of MODES) {
    const s = similar(pool, id, { mode, k });
    if (!s || !s.length) continue;
    for (const x of s) { out.packs[x.source_id] = x.pack; delete x.pack; } // titulek packu jednou, ne v každém řádku
    out[mode][id] = s;
  }
  return out;
}
