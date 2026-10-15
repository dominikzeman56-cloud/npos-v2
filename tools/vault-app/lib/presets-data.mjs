// Preset index for the "Presety" page: merges data/presets/index/*.jsonl (tools/index_presets.py) with pack
// titles from knowledge/sources.jsonl. Only the compact index goes out; full preset dumps (_local/) never do.
import fs from 'node:fs/promises';
import path from 'node:path';

const readJsonl = async (file) =>
  (await fs.readFile(file, 'utf8')).split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));

export async function loadPresets(repoRoot) {
  const dir = path.join(repoRoot, 'data', 'presets', 'index');
  let files = [];
  try { files = (await fs.readdir(dir)).filter((f) => f.endsWith('.jsonl')).sort(); } catch { /* no index yet */ }
  const sources = new Map();
  try { for (const s of await readJsonl(path.join(repoRoot, 'knowledge', 'sources.jsonl'))) sources.set(s.id, s); } catch { /* optional */ }

  const presets = [];
  for (const f of files) {
    for (const r of await readJsonl(path.join(dir, f))) {
      const { file: _file, ...keep } = r; // file name adds nothing over name + group
      presets.push(keep);
    }
  }
  const counts = new Map();
  for (const p of presets) counts.set(p.source_id, (counts.get(p.source_id) || 0) + 1);
  const packs = [...counts].map(([id, count]) => ({
    id, count,
    title: sources.get(id)?.title || id,
    author: sources.get(id)?.author || '',
  })).sort((a, b) => b.count - a.count);
  return { generated: new Date().toISOString().slice(0, 10), packs, presets };
}

// ---- build view (stavba presetu) ----------------------------------------------------------------
// Reads the FULL local dump (data/presets/_local/<pack>/<id>.json). Those come from paid packs
// (redistribution: none), so the static export only includes them with --builds.
const ID_RE = /^[a-z0-9][a-z0-9-]*$/;

export async function loadBuild(repoRoot, id) {
  if (!ID_RE.test(id || '')) return null;
  const root = path.join(repoRoot, 'data', 'presets', '_local');
  let packs = [];
  try { packs = await fs.readdir(root); } catch { return null; }
  for (const pack of packs) {
    try {
      const d = JSON.parse(await fs.readFile(path.join(root, pack, `${id}.json`), 'utf8'));
      return buildView(d);
    } catch { /* not in this pack */ }
  }
  return null;
}

export function buildView(d) {
  const r = d.reading || {};
  const num = (v) => (typeof v === 'number' ? v : null);
  return {
    id: d.id, name: d.name, synth: d.synth,
    oscillators: (r.oscillators || []).map((o) => ({
      slot: o.slot, enabled: !!o.enabled, kind: o.kind || null, table: o.table_name || o.wavetable || null,
      octave: num(o.params?.kParamOctave), pitch: num(o.params?.kParamPitch), fine: num(o.params?.kParamFine),
      level: num(o.params?.kParamVolume), unison: o.unison_voices, detune: num(o.params?.kParamDetune),
      detune_wid: num(o.params?.kParamDetuneWid), pan: num(o.params?.kParamPan),
      warp: o.kind_params?.kParamWarpMenu || null, warp_amt: num(o.kind_params?.kParamWarp),
      warp2: o.kind_params?.kParamWarpMenu2 || null, warp2_amt: num(o.kind_params?.kParamWarp2),
      table_pos: num(o.kind_params?.kParamTablePos), random_phase: num(o.kind_params?.kParamRandomPhase),
    })),
    filters: (r.voice_filters || []).map((f) => ({
      slot: f.slot, on: f.params?.kParamEnable !== 0, type: f.params?.kParamType || null,
      freq: num(f.params?.kParamFreq), reso: num(f.params?.kParamReso), drive: num(f.params?.kParamDrive), wet: num(f.params?.kParamWet),
    })),
    fx: (r.fx || []).map((e) => ({
      index: e.index, module: e.module, on: e.params?.kParamEnable !== 0,
      mode: e.params?.kParamMode || e.params?.kParamType || null,
      params: Object.fromEntries(Object.entries(e.params || {})
        .filter(([k, v]) => !['kParamEnable', 'kParamMode', 'kParamType'].includes(k) && typeof v === 'number')),
    })),
    modulation: (r.modulation || []).map((m) => ({ source: m.source, dest: `${m.dest_module}${m.dest_module_id ?? ''}`, param: (m.dest_param || '').replace(/^kParam/, ''), amount: m.amount })),
    lfos: (r.lfos || []).map((l) => ({ index: l.index, mode: l.params?.kParamMode || null, rate: num(l.params?.kParamRate), shape: l.shape || null, points: l.curve_points ?? null, type: l.params?.kParamType || null })),
    macros: (r.macros || []).map((m) => ({ index: m.index, value: num(m.params?.kParamValue) })),
    voice: r.voice || {},
  };
}
