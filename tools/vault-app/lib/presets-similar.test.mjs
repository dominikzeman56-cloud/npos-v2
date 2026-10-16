import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { audioVector, loadPool, similar, similarAll } from './presets-similar.mjs';

const KEYS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'];
const feat = (base, shift = 0) => Object.fromEntries(KEYS.map((k, i) => [k, base + i * 0.1 + shift]));
const write = (file, rows) => fs.writeFile(file, rows.map((r) => JSON.stringify(r)).join('\n') + '\n');

async function fixture() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'sim-test-'));
  for (const d of ['index', 'fxp', 'features', 'audio']) await fs.mkdir(path.join(root, 'data', 'presets', d), { recursive: true });
  await fs.mkdir(path.join(root, 'knowledge'));
  await write(path.join(root, 'knowledge', 'sources.jsonl'), [{ id: 'p', title: 'Pack P' }]);
  const meta = (id, name) => ({ id, source_id: 'p', name, role: 'bass', synth: 'x' });
  await write(path.join(root, 'data', 'presets', 'index', 'p.jsonl'), [meta('q', 'Query'), meta('near', 'Near'), meta('far', 'Far'), meta('few', 'Few keys')]);
  // 6 presetů s rozptylem, aby měl každý klíč nenulovou směrodatnou odchylku
  const rows = [['q', feat(1)], ['near', feat(1, 0.05)], ['far', feat(5)], ['few', { a: 1, b: 1 }], ['x1', feat(2)], ['x2', feat(3)], ['x3', feat(4)]];
  await write(path.join(root, 'data', 'presets', 'fxp', 'p.jsonl'), ['x1', 'x2', 'x3'].map((id) => meta(id, id.toUpperCase())));
  await write(path.join(root, 'data', 'presets', 'features', 'p.jsonl'), rows.map(([id, f]) => ({ id, source_id: 'p', features: f })));
  await write(path.join(root, 'data', 'presets', 'features', 'orphan.jsonl'), [{ id: 'bez-jmena', features: feat(1) }]);
  const au = (v) => ({ rms_db: -10 - v, crest_db: 5 + v, band_sub_pct: 50 + v, band_low_pct: 20, band_mid_pct: 20 - v, band_high_pct: 5, band_air_pct: 5 + v,
    centroid_hz: 500 + 100 * v, rolloff85_hz: 400 + 50 * v, harmonic_pct: 30 + v, am_depth: 0.1 * v, side_minus_mid_db: -5, upper_db: -8 + v, window: 'sustain' });
  await write(path.join(root, 'data', 'presets', 'audio', 'p.jsonl'), [['q', 0], ['near', 0.2], ['far', 9], ['x1', 3], ['x2', 6], ['x3', 8]]
    .map(([id, v]) => ({ id, audio: au(v) })).concat([{ id: 'few', audio: { silent: true } }]));
  return root;
}

test('similar ranks by z-scored distance and never returns the query itself', async () => {
  const pool = await loadPool(await fixture());
  const s = similar(pool, 'q', { k: 3 });
  assert.equal(s[0].id, 'near');
  assert.ok(!s.some((x) => x.id === 'q'));
  assert.ok(s[0].d < s[1].d);
  assert.equal(s[0].name, 'Near');
  assert.equal(s[0].pack, 'Pack P');
});

test('presets with fewer shared keys than the minimum are not compared', async () => {
  const pool = await loadPool(await fixture());
  assert.ok(!similar(pool, 'q', { k: 20 }).some((x) => x.id === 'few'));
  assert.deepEqual(similar(pool, 'few'), []);
});

test('unknown id, unknown mode and features without a name row give null', async () => {
  const pool = await loadPool(await fixture());
  assert.equal(similar(pool, 'neexistuje'), null);
  assert.equal(similar(pool, 'bez-jmena'), null);
  assert.equal(similar(pool, 'q', { mode: 'wav' }), null);
});

test('audio mode uses render descriptors and skips silent renders', async () => {
  const pool = await loadPool(await fixture());
  const s = similar(pool, 'q', { mode: 'audio', k: 5 });
  assert.equal(s[0].id, 'near');
  assert.ok(!s.some((x) => x.id === 'few'));
  assert.equal(similar(pool, 'few', { mode: 'audio' }), null);
});

test('audioVector applies the same transforms as preset_roles.py', () => {
  const v = audioVector({ centroid_hz: 1000, am_depth: 0, side_minus_mid_db: -138, window: 'attack', rms_db: null });
  assert.equal(v.centroid_hz, 3);
  assert.equal(v.am_depth, 0);
  assert.equal(v.side_minus_mid_db, -40);
  assert.equal(v.attack, 1);
  assert.ok(!('rms_db' in v));
});

test('similarAll exports only numbers, ids, names and pack titles (no audio, no files, no wavetables)', async () => {
  const pool = await loadPool(await fixture());
  const all = similarAll(pool, ['q', 'near']);
  assert.ok(all.params.q.length && all.audio.q.length);
  assert.match(all.note, /ne poslech/);
  const text = JSON.stringify(all);
  assert.ok(!/\.wav|\.fxp|wavetable|[A-Z]:[\/]/i.test(text));
  assert.deepEqual(Object.keys(all.params.q[0]).sort(), ['d', 'id', 'n', 'name', 'role', 'source_id']);
  assert.equal(all.packs.p, 'Pack P');
});
