import test from 'node:test';
import assert from 'node:assert/strict';
import { syncRateHz, midiToHz, noteName, centsFromEqual, buildTable, distCurve, TABLE_KINDS, SIZE, FRAMES, MAXH } from './public/trainer-core.js';
import { Engine, defaults, lfoValue } from './public/trainer-dsp.js';

const SR = 48000;
const tableCache = new Map();
const table = (i) => { if (!tableCache.has(i)) tableCache.set(i, buildTable(i)); return tableCache.get(i); };

function render(set, secs = 1, f0 = 41.2) {
  const e = new Engine(SR, TABLE_KINDS.map((_, i) => table(i)));
  e.set(set);
  e.noteOn(f0);
  const n = Math.floor(secs * SR);
  const out = new Float32Array(n), c = new Float32Array(n), d = new Float32Array(n);
  for (let o = 0; o < n; o += 128) {
    const m = Math.min(128, n - o);
    e.process(out.subarray(o, o + m), c.subarray(o, o + m), d.subarray(o, o + m), m);
  }
  return { out, c, d };
}
const rms = (x, a = 0, b = x.length) => { let s = 0; for (let i = a; i < b; i++) s += x[i] * x[i]; return Math.sqrt(s / (b - a)); };
function goertzel(x, f, a = 0, b = x.length) {      // Hannovo okno, ať netekou sousední harmonické do měření
  const w = (2 * Math.PI * f) / SR; let re = 0, im = 0, g = 0;
  for (let i = a; i < b; i++) { const h = 0.5 - 0.5 * Math.cos((2 * Math.PI * (i - a)) / (b - a)); g += h; re += h * x[i] * Math.cos(w * i); im += h * x[i] * Math.sin(w * i); }
  return (2 * Math.hypot(re, im)) / g;
}
const db = (x) => 20 * Math.log10(Math.max(x, 1e-12));

test('tempo-synced LFO rate at 174 BPM matches the canon numbers (1/4 ≈ 2.9 Hz, 1/8 ≈ 5.8, 1/16 ≈ 11.6)', () => {
  assert.ok(Math.abs(syncRateHz(174, '1/4') - 2.9) < 1e-9);
  assert.ok(Math.abs(syncRateHz(174, '1/8') - 5.8) < 1e-9);
  assert.ok(Math.abs(syncRateHz(174, '1/16') - 11.6) < 1e-9);
  assert.ok(Math.abs(syncRateHz(120, '1/1') - 0.5) < 1e-9);
});

test('pitch and ratio helpers: E1 = 41.2 Hz, FM bin 5 is 14 ct flat of a major third, bin 7 is 31 ct flat', () => {
  assert.ok(Math.abs(midiToHz(28) - 41.2) < 0.01);
  assert.equal(noteName(28), 'E1');
  assert.ok(Math.abs(centsFromEqual(5).dev - -13.7) < 0.1);
  assert.ok(Math.abs(centsFromEqual(7).dev - -31.2) < 0.1);
  assert.ok(Math.abs(centsFromEqual(2).dev) < 1e-9);
});

test('wavetables are normalised, band-limited per mip and the last sample repeats the first', () => {
  for (let k = 0; k < TABLE_KINDS.length; k++) {
    const t = table(k);
    assert.equal(t.mips.length, MAXH.length);
    for (let f = 0; f < FRAMES; f++) {
      const base = f * (SIZE + 1);
      let pk = 0;
      for (let n = 0; n < SIZE; n++) pk = Math.max(pk, Math.abs(t.mips[0][base + n]));
      assert.ok(Math.abs(pk - 1) < 1e-4, `${TABLE_KINDS[k].id} frame ${f} peak ${pk}`);
      assert.equal(t.mips[0][base + SIZE], t.mips[0][base]);
    }
  }
  // poslední mip (4 harmonické) nesmí nést nic nad 4. harmonickou
  const cyc = Float64Array.from({ length: SIZE }, (_, n) => table(1).mips[MAXH.length - 1][n]);
  const h = (k) => { let re = 0, im = 0; for (let n = 0; n < SIZE; n++) { re += cyc[n] * Math.cos((2 * Math.PI * k * n) / SIZE); im += cyc[n] * Math.sin((2 * Math.PI * k * n) / SIZE); } return Math.hypot(re, im) / SIZE; };
  assert.ok(h(3) > 0.05 && h(5) < 1e-6 && h(40) < 1e-6);
});

test('a sine table plays a pure tone at the played pitch', () => {
  const { out } = render({ table: 0, env: { a: 0.001, d: 0.01, s: 1, r: 0.1 } }, 1);
  const a = 24000, b = 48000;
  const f1 = goertzel(out, 41.2, a, b);
  assert.ok(f1 > 0.5, `fundament ${f1}`);
  assert.ok(db(f1) - db(goertzel(out, 82.4, a, b)) > 40);
});

test('two identical voices with inverted polarity cancel to silence (phase cancellation lesson); detune brings the sound back', () => {
  const base = { table: 1, unison: 2, detune: 0, invert2: true, env: { a: 0.001, d: 0.01, s: 1, r: 0.1 } };
  assert.ok(rms(render(base, 0.5).out, 4000) < 1e-6);
  assert.ok(rms(render({ ...base, invert2: false }, 0.5).out, 4000) > 0.1);
  assert.ok(rms(render({ ...base, detune: 20 }, 0.5).out, 4000) > 0.05);
});

test('voices added in the middle of a note start in phase, so inverted twins still cancel', () => {
  const e = new Engine(SR, TABLE_KINDS.map((_, i) => table(i)));
  e.set({ table: 1, unison: 1, env: { a: 0.001, d: 0.01, s: 1, r: 0.1 } });
  e.noteOn(41.2);
  const buf = () => [new Float32Array(128), new Float32Array(128), new Float32Array(128)];
  for (let i = 0; i < 100; i++) { const [o, c, d] = buf(); e.process(o, c, d, 128); }      // hraje jeden hlas
  e.set({ unison: 2, detune: 0, invert2: true });
  let r = 0; for (let i = 0; i < 20; i++) { const [o, c, d] = buf(); e.process(o, c, d, 128); r = rms(o); }
  assert.ok(r < 1e-6, `rms ${r}`);
});

test('small unison detune makes the level beat in time (reese "LFO without LFO")', () => {
  // sinus bez harmonických ukáže čisté zázněje: 25 ct = ~0,6 Hz rozdíl, období ~1,7 s
  const { out } = render({ table: 0, unison: 2, detune: 25, env: { a: 0.001, d: 0.01, s: 1, r: 0.1 } }, 3);
  const win = 2400; const levels = [];
  for (let i = 4000; i + win < out.length; i += win) levels.push(rms(out, i, i + win));
  assert.ok(Math.max(...levels) / Math.min(...levels) > 3);
});

test('FM (phase modulation) adds sidebands; a bigger index adds more upper energy', () => {
  const env = { a: 0.001, d: 0.01, s: 1, r: 0.1 };
  const upper = (o) => { let s = 0; for (let k = 4; k <= 12; k++) s += goertzel(o, 41.2 * k, 12000, 48000) ** 2; return s; };
  const none = upper(render({ table: 0, env }, 1).out);
  const fm = upper(render({ table: 0, modRatio: 3, fmIndex: 4, env }, 1).out);
  assert.ok(fm > 100 * none + 1e-6, `${fm} vs ${none}`);
});

test('AM by the modulator oscillator puts sidebands at f0 ± ratio·f0', () => {
  const env = { a: 0.001, d: 0.01, s: 1, r: 0.1 };
  const o = render({ table: 0, modRatio: 3, amDepth: 1, env }, 1).out;
  assert.ok(goertzel(o, 41.2 * 2, 12000, 48000) > 0.05 && goertzel(o, 41.2 * 4, 12000, 48000) > 0.05);
  assert.ok(goertzel(o, 41.2, 12000, 48000) > 0.05);
});

test('LFO square on amp at 1/16 (11.6 Hz) gates the sound: windows alternate between loud and silent', () => {
  const lfo = [{ shape: 'square', rate: syncRateHz(174, '1/16'), depth: 1, target: 'amp', trigger: true }, { target: 'none' }];
  const { out } = render({ table: 1, lfo, env: { a: 0.001, d: 0.01, s: 1, r: 0.1 } }, 1);
  const half = Math.round(SR / syncRateHz(174, '1/16') / 2);
  const w = []; for (let i = half; i + half <= out.length - half; i += half) w.push(rms(out, i + 200, i + half - 200));
  assert.ok(Math.min(...w) < 0.05 * Math.max(...w));
});

test('LFO targeting cutoff or drive leaves audio alone and writes the modulation channels', () => {
  const lfo = [{ shape: 'sine', rate: 5, depth: 0.5, target: 'cutoff', trigger: true }, { shape: 'tri', rate: 3, depth: 1, target: 'drive', trigger: true }];
  const { out, c, d } = render({ table: 1, lfo }, 1);
  assert.ok(Math.max(...c.slice(0, 48000)) > 0.45 && Math.min(...c) < -0.45);
  assert.ok(Math.max(...d) > 0.95);
  const plain = render({ table: 1 }, 1).out;
  assert.deepEqual(Array.from(out.slice(0, 100)), Array.from(plain.slice(0, 100)));
});

test('LFO shapes stay within −1..1', () => {
  for (const s of ['sine', 'tri', 'saw', 'square']) for (let i = 0; i <= 100; i++) assert.ok(Math.abs(lfoValue(s, i / 100)) <= 1 + 1e-12);
});

test('trigger LFO restarts on every note, free-running LFO does not', () => {
  const mk = (trigger) => { const e = new Engine(SR, [table(0)]); e.set({ lfo: [{ rate: 7, depth: 1, target: 'cutoff', shape: 'sine', trigger }, {}] }); e.noteOn(41.2); const a = new Float32Array(128), b = new Float32Array(128), c = new Float32Array(128); e.process(a, b, c, 128); e.noteOff(); e.noteOn(41.2); e.process(a, b, c, 128); return b[0]; };
  assert.ok(Math.abs(mk(true)) < 0.01);
  assert.ok(Math.abs(mk(false)) > 0.01);
});

test('distortion curves: soft/hard/fold are odd (no DC), asymmetric one is not and stays finite', () => {
  const dcOf = (type) => { const c = distCurve(type); let s = 0; const N = 2000; for (let i = 0; i < N; i++) { const x = Math.sin((2 * Math.PI * i) / N) * 4 / 16; const idx = Math.round(((x + 1) / 2) * (c.length - 1)); s += c[idx]; } return s / N; };
  for (const t of ['soft', 'hard', 'fold']) assert.ok(Math.abs(dcOf(t)) < 1e-3, t);
  assert.ok(Math.abs(dcOf('asym')) > 0.05);
  for (const t of ['soft', 'hard', 'fold', 'asym']) assert.ok(distCurve(t).every((v) => Number.isFinite(v) && Math.abs(v) <= 2));
});

test('defaults are independent objects', () => {
  const a = defaults(), b = defaults();
  a.lfo[0].rate = 99; a.env.a = 9;
  assert.equal(b.lfo[0].rate, 2.9); assert.equal(b.env.a, 0.005);
});
