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
