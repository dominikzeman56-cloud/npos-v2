import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildView, loadBuild, loadPresets } from './presets-data.mjs';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

const dump = {
  id: 'x-test', name: 'Test', synth: 'Serum2',
  reading: {
    oscillators: [
      { slot: 0, enabled: true, kind: 'WTOsc', unison_voices: 3, params: { kParamVolume: 80 }, kind_params: { kParamWarpMenu: 'kPD_OSC', kParamWarp: 40 } },
      { slot: 3, enabled: true, params: { kParamVolume: 20 } },
      { slot: 4, enabled: false, params: {} },
    ],
    voice_filters: [{ slot: 0, params: { kParamType: 'LP', kParamFreq: 50 } }],
    fx: [{ index: 0, module: 'FXDistortion', params: { kParamWet: 100, kParamEnable: 1, kParamMode: 'Tube' } }],
    modulation: [{ source: 'LFO 1', dest_module: 'VoiceFilter', dest_module_id: 0, dest_param: 'kParamFreq', amount: 30, extra: { kParamBipolar: 1 } }],
    lfos: [{ index: 0, params: { kParamRate: 2 }, curve: { x: [0, 0.5, 1], y: [1, 0, 1], c: [0.5, 0.5, 0.5] }, curve_points: 2 }],
    envs: [{ index: 0, params: { kParamAttack: 0.1 } }],
    macros: [{ index: 0, name: 'Cutoff', params: { kParamValue: 50 } }],
    voice: { kParamMonoToggle: 1 },
  },
};

test('buildView splits oscillators A-C from Noise and Sub', () => {
  const v = buildView(dump);
  assert.equal(v.oscillators.length, 1);
  assert.equal(v.oscillators[0].unison, 3);
  assert.equal(v.oscillators[0].warp, 'kPD_OSC');
  assert.equal(v.noise.enabled, true);
  assert.equal(v.noise.level, 20);
  assert.equal(v.sub.enabled, false);
});

test('buildView keeps LFO curve points, envelopes, macros names and modulation extras', () => {
  const v = buildView(dump);
  assert.equal(v.lfos[0].points, 3);
  assert.equal(v.lfos[0].segments, 2);
  assert.deepEqual(v.lfos[0].curve.x, [0, 0.5, 1]);
  assert.equal(v.envs[0].params.kParamAttack, 0.1);
  assert.equal(v.macros[0].name, 'Cutoff');
  assert.equal(v.modulation[0].extra.kParamBipolar, 1);
  assert.equal(v.fx[0].on, true);
});

test('buildView tolerates an empty reading', () => {
  const v = buildView({ id: 'e', name: 'E', synth: '', reading: {} });
  assert.deepEqual(v.lfos, []);
  assert.equal(v.noise.enabled, false);
});

test('loadBuild rejects ids that could escape the dump folder', async () => {
  assert.equal(await loadBuild(REPO, '../x'), null);
  assert.equal(await loadBuild(REPO, 'A/B'), null);
  assert.equal(await loadBuild(REPO, ''), null);
});

test('loadPresets reads the committed compact index with pack metadata', async () => {
  const d = await loadPresets(REPO);
  assert.ok(d.presets.length > 100);
  assert.ok(d.packs.length >= 1);
  assert.ok(d.presets.every((p) => p.id && p.name));
});
