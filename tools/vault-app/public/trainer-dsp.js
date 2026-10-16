// Jádro trenažéru: jeden monofonní hlas (wavetable + unison + FM(PM) + AM + 2 LFO + obálka). Čistý JS bez Web Audio, proto
// ho používá AudioWorklet (trainer-worklet.js) i testy v Node. Filtr a zkreslení jsou nativní uzly v prohlížeči.
import { FRAMES, SIZE, MAXH } from './trainer-core.js';

const TAU = Math.PI * 2;
export const MAX_UNISON = 7;
export const LFO_SHAPES = ['sine', 'tri', 'saw', 'square'];
export const LFO_TARGETS = ['none', 'cutoff', 'wt', 'pitch', 'fm', 'amp', 'drive'];

export function defaults() {
  const lfo = () => ({ shape: 'sine', rate: 2.9, depth: 0, target: 'none', trigger: true });
  return {
    table: 0, wtPos: 0, level: 1,
    unison: 1, detune: 0, phaseMode: 'zero', invert2: false,
    modRatio: 2, fmIndex: 0, amDepth: 0,
    env: { a: 0.005, d: 0.2, s: 0.8, r: 0.15 },
    lfo: [lfo(), lfo()],
  };
}

export const lfoValue = (shape, ph) =>
  shape === 'sine' ? Math.sin(TAU * ph) : shape === 'tri' ? 1 - 4 * Math.abs(ph - 0.5) : shape === 'saw' ? 1 - 2 * ph : ph < 0.5 ? 1 : -1;

export class Engine {
  constructor(sr = 48000, tables = []) {
    this.sr = sr;
    this.tables = tables;          // tables[i] = výstup buildTable()
    this.p = defaults();
    this.ph = new Float64Array(MAX_UNISON);
    this.phB = 0;
    this.lfoPh = [0, 0];
    this.freq = 41.2;
    this.stage = 'idle';
    this.env = 0;
    this.seed = 12345;
    this._n = 1;                   // počet hlasů v minulém bloku
  }

  rand() { this.seed = (this.seed * 1664525 + 1013904223) >>> 0; return this.seed / 4294967296; }

  set(p) {                          // sloučí změny parametrů (mělké sloučení po sekcích)
    for (const k of Object.keys(p)) {
      if (k === 'env') Object.assign(this.p.env, p.env);
      else if (k === 'lfo') p.lfo.forEach((l, i) => l && Object.assign(this.p.lfo[i], l));
      else this.p[k] = p[k];
    }
  }

  noteOn(freq) {
    this.freq = freq;
    this.stage = 'attack';
    for (let u = 0; u < MAX_UNISON; u++) this.ph[u] = this.p.phaseMode === 'random' ? this.rand() : 0;
    this.phB = 0;
    this.p.lfo.forEach((l, i) => { if (l.trigger) this.lfoPh[i] = 0; });
  }

  noteOff() { if (this.stage !== 'idle') this.stage = 'release'; }

  get active() { return this.stage !== 'idle'; }

  _env() {
    const { a, d, s, r } = this.p.env, sr = this.sr;
    if (this.stage === 'attack') { this.env += 1 / Math.max(1, a * sr); if (this.env >= 1) { this.env = 1; this.stage = 'decay'; } }
    else if (this.stage === 'decay') { this.env -= (1 - s) / Math.max(1, d * sr); if (this.env <= s) { this.env = s; this.stage = 'sustain'; } }
    else if (this.stage === 'release') { this.env -= this._relStep; if (this.env <= 1e-5) { this.env = 0; this.stage = 'idle'; } }
    return this.env;
  }

  _read(tbl, ph, f, pos) {
    const maxAllowed = Math.max(1, Math.floor((0.5 * this.sr) / f));
    let m = MAXH.findIndex((h) => h <= maxAllowed);
    if (m < 0) m = MAXH.length - 1;
    const data = tbl.mips[m];
    const ff = Math.min(Math.max(pos, 0), 1) * (FRAMES - 1);
    const f0 = Math.min(FRAMES - 2, Math.floor(ff)), fr = ff - f0;
    const x = ph * SIZE, i = Math.floor(x), fi = x - i;
    const b0 = f0 * (SIZE + 1) + i, b1 = b0 + (SIZE + 1);
    const v0 = data[b0] + (data[b0 + 1] - data[b0]) * fi;
    const v1 = data[b1] + (data[b1 + 1] - data[b1]) * fi;
    return v0 + (v1 - v0) * fr;
  }

  // Zapíše n vzorků: out = zvuk, cutMod = modulace cutoffu (−1..1), drvMod = modulace driveu (−1..1)
  process(out, cutMod, drvMod, n) {
    const p = this.p, sr = this.sr;
    const tbl = this.tables[p.table];
    if (!tbl || this.stage === 'idle') { out.fill(0, 0, n); cutMod.fill(0, 0, n); drvMod.fill(0, 0, n); return; }
    if (this.stage === 'release' && !this._relStep) this._relStep = Math.max(this.env, 1e-3) / Math.max(1, p.env.r * sr);
    if (this.stage !== 'release') this._relStep = 0;
    const N = Math.max(1, Math.min(MAX_UNISON, p.unison | 0));
    // hlasy, které se právě přidaly, nesmějí mít zastaralou fázi (jinak se dva stejné hlasy neruší, i když mají)
    for (let u = this._n; u < N; u++) this.ph[u] = p.phaseMode === 'random' ? this.rand() : this.ph[0];
    this._n = N;
    const offs = [];
    for (let u = 0; u < N; u++) offs.push(N === 1 ? 0 : N === 2 ? (u === 0 ? 0 : p.detune) : ((u - (N - 1) / 2) / ((N - 1) / 2)) * p.detune);
    const norm = 1 / N;
    for (let s = 0; s < n; s++) {
      let pitchC = 0, wtOff = 0, fmMul = 1, gate = 1, cm = 0, dm = 0;
      for (let i = 0; i < 2; i++) {
        const l = p.lfo[i];
        this.lfoPh[i] += l.rate / sr; if (this.lfoPh[i] >= 1) this.lfoPh[i] -= Math.floor(this.lfoPh[i]);
        if (l.target === 'none' || l.depth === 0) continue;
        const v = lfoValue(l.shape, this.lfoPh[i]) * l.depth;
        if (l.target === 'pitch') pitchC += v * 1200;
        else if (l.target === 'wt') wtOff += v * 0.5;
        else if (l.target === 'fm') fmMul += v;
        else if (l.target === 'amp') gate *= 1 - l.depth * (0.5 - 0.5 * lfoValue(l.shape, this.lfoPh[i]));
        else if (l.target === 'cutoff') cm += v;
        else if (l.target === 'drive') dm += v;
      }
      const fP = this.freq * 2 ** (pitchC / 1200);
      this.phB += (fP * p.modRatio) / sr; this.phB -= Math.floor(this.phB);
      const sB = Math.sin(TAU * this.phB);
      const pm = (Math.max(0, p.fmIndex * fmMul) * sB) / TAU;
      const pos = p.wtPos + wtOff;
      let acc = 0;
      for (let u = 0; u < N; u++) {
        const fu = fP * 2 ** (offs[u] / 1200);
        this.ph[u] += fu / sr; this.ph[u] -= Math.floor(this.ph[u]);
        let q = this.ph[u] + pm; q -= Math.floor(q);
        const v = this._read(tbl, q, fu, pos);
        acc += p.invert2 && u === 1 ? -v : v;
      }
      const am = 1 - p.amDepth + p.amDepth * (0.5 + 0.5 * sB);
      out[s] = acc * norm * this._env() * p.level * am * gate;
      cutMod[s] = Math.max(-1, Math.min(1, cm));
      drvMod[s] = Math.max(-1, Math.min(1, dm));
    }
  }
}
