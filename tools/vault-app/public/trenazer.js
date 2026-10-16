// Trenažér syntézy: UI, zvukový graf a lekce. Jádro (wavetable, hlas, LFO, obálka) je v trainer-core.js a trainer-dsp.js.
// Nic se neukládá ani neexportuje a nepoužívají se žádná data presetů.
import { TABLE_KINDS, DIST_TYPES, DIVISIONS, CURVE_RANGE, FRAMES, SIZE, buildTable, distCurve, syncRateHz, midiToHz, noteName, centsFromEqual } from './trainer-core.js';
import { LFO_SHAPES, LFO_TARGETS } from './trainer-dsp.js';

const $ = (s) => document.querySelector(s);
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const F0_REF = 41.2;                                 // E1: při key trackingu 100 % je cutoff zadaný pro tuto notu
const DEFAULT = () => ({
  table: 1, wtPos: 0, unison: 1, detune: 0, phaseMode: 'zero', invert2: false,
  modRatio: 2, fmIndex: 0, amDepth: 0,
  lfo: [0, 1].map(() => ({ shape: 'sine', mode: 'sync', hz: 2.9, div: '1/4', depth: 0, target: 'none', trigger: true })),
  filt: { type: 'lowpass', cutoff: 4000, res: 0.15, slope: 12, kt: 0 },
  d1: { type: 'off', drive: 0 }, d2: { type: 'off', drive: 0 }, between: false, trim: 0, dcBlock: true,
  env: { a: 0.005, d: 0.3, s: 0.8, r: 0.2 },
});
let S = DEFAULT();
let rootNote = 28;                                   // E1
let bpm = 174;

// ── pomocné: cesty ve stavu, slučování ────────────────────────────────────────────────────────────────────────
const getP = (path) => path.split('.').reduce((o, k) => o[k], S);
const setP = (path, v) => { const ks = path.split('.'); const last = ks.pop(); ks.reduce((o, k) => o[k], S)[last] = v; };
const merge = (t, p) => { for (const k of Object.keys(p)) { if (p[k] && typeof p[k] === 'object') merge(t[k], p[k]); else t[k] = p[k]; } return t; };

// ── zobrazení hodnot ──────────────────────────────────────────────────────────────────────────────────────────
const fHz = (v) => (v >= 1000 ? (v / 1000).toFixed(2) + ' kHz' : v.toFixed(v < 10 ? 2 : 0) + ' Hz');
const fS = (v) => (v < 1 ? Math.round(v * 1000) + ' ms' : v.toFixed(2) + ' s');
const logMap = (min, max) => ({ to: (p) => min * (max / min) ** (p / 1000), from: (v) => (1000 * Math.log(v / min)) / Math.log(max / min), min: 0, max: 1000, step: 1 });

// ── specifikace ovládání ──────────────────────────────────────────────────────────────────────────────────────
const tableOpts = TABLE_KINDS.map((k, i) => [i, k.name]);
const divOpts = DIVISIONS.map((d) => [d[0], d[0]]);
const lfoCtl = (i) => {
  const p = `lfo.${i}.`;
  return [
    { sub: `LFO ${i + 1}` },
    { id: p + 'target', label: 'Cíl', type: 'select', opts: [['none', 'vypnuto'], ['cutoff', 'cutoff filtru'], ['wt', 'pozice wavetable'], ['pitch', 'výška (±1 okt.)'], ['fm', 'FM index'], ['amp', 'hlasitost (AM / gate)'], ['drive', 'drive 1. zkreslení']] },
    { id: p + 'shape', label: 'Tvar', type: 'select', opts: [['sine', 'sinus'], ['tri', 'trojúhelník'], ['saw', 'pila dolů'], ['square', 'obdélník']] },
    { id: p + 'mode', label: 'Rychlost', type: 'select', opts: [['sync', 'podle tempa'], ['hz', 'v Hz']] },
    { id: p + 'div', label: 'Dělení', type: 'select', opts: divOpts, show: () => S.lfo[i].mode === 'sync' },
    { id: p + 'hz', label: 'Rychlost Hz', type: 'range', ...logMap(0.05, 40), fmt: fHz, show: () => S.lfo[i].mode === 'hz', log: [0.05, 40] },
    { id: p + 'depth', label: 'Hloubka', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + ' %' },
    { id: p + 'trigger', label: 'Trigger', type: 'check', text: 'restart cyklu při každé notě' },
    { note: () => `Rychlost: ${lfoRate(i).toFixed(2)} Hz` },
  ];
};
const SPEC = [
  { group: 'Oscilátor a wavetable', open: true, items: [
    { id: 'table', label: 'Wavetable', type: 'select', opts: tableOpts, num: true },
    { id: 'wtPos', label: 'Pozice', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => v.toFixed(2) },
    { sub: 'Unison' },
    { id: 'unison', label: 'Hlasů', type: 'range', min: 1, max: 7, step: 1, fmt: (v) => String(v) },
    { id: 'detune', label: 'Detune', type: 'range', min: 0, max: 50, step: 0.5, fmt: (v) => v.toFixed(1) + ' ct' },
    { id: 'phaseMode', label: 'Fáze', type: 'select', opts: [['zero', 'nula při každé notě'], ['random', 'náhodná']] },
    { id: 'invert2', label: '2. hlas', type: 'check', text: 'obrátit polaritu (jen unison ≥ 2)' },
  ] },
  { group: 'FM a AM', open: true, items: [
    { id: 'modRatio', label: 'Poměr modulátoru', type: 'select', opts: [0.5, 1, 2, 3, 4, 5, 6, 7, 8].map((r) => [r, r + '× f0']), num: true },
    { note: () => { const c = centsFromEqual(S.modRatio); return `${(S.modRatio * curF0()).toFixed(1)} Hz, ${c.dev >= 0 ? '+' : '−'}${Math.abs(c.dev).toFixed(0)} ct od půltónové mřížky (bin N = N × fundament, ne N půltónů)`; } },
    { id: 'fmIndex', label: 'FM index', type: 'range', min: 0, max: 10, step: 0.1, fmt: (v) => v.toFixed(1), note: 'FM je tady fázová modulace (PM), jako v Serum.' },
    { id: 'amDepth', label: 'AM hloubka', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + ' %', note: 'AM nese stejný modulátor jako FM: vznikají postranní pásma f0 ± poměr × f0.' },
  ] },
  { group: 'LFO 1 a 2', open: false, items: [...lfoCtl(0), ...lfoCtl(1)] },
  { group: 'Filtr', open: true, items: [
    { id: 'filt.type', label: 'Typ', type: 'select', opts: [['lowpass', 'dolní propust'], ['highpass', 'horní propust'], ['bandpass', 'pásmová propust']] },
    { id: 'filt.cutoff', label: 'Cutoff', type: 'range', ...logMap(20, 18000), fmt: fHz, log: [20, 18000] },
    { note: () => `= ${(S.filt.cutoff / curF0()).toFixed(2)} × f0 (základní tón ${curF0().toFixed(1)} Hz)` },
    { id: 'filt.res', label: 'Rezonance', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + ' %' },
    { id: 'filt.slope', label: 'Sklon', type: 'select', opts: [[12, '12 dB/okt.'], [24, '24 dB/okt. (2 filtry za sebou)']], num: true },
    { id: 'filt.kt', label: 'Key tracking', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + ' %', note: 'Cutoff je zadaný pro E1; při 100 % se filtr posouvá s notou.' },
  ] },
  { group: 'Zkreslení', open: true, items: [
    { sub: '1. stupeň' },
    { id: 'd1.type', label: 'Typ', type: 'select', opts: [['off', 'vypnuto'], ...DIST_TYPES.map((d) => [d.id, d.name])] },
    { id: 'd1.drive', label: 'Vstupní gain', type: 'range', min: 0, max: 24, step: 0.5, fmt: (v) => '+' + v.toFixed(1) + ' dB' },
    { id: 'between', label: 'EQ mezi', type: 'check', text: 'řez pod 350 Hz mezi stupni' },
    { sub: '2. stupeň' },
    { id: 'd2.type', label: 'Typ', type: 'select', opts: [['off', 'vypnuto'], ...DIST_TYPES.map((d) => [d.id, d.name])] },
    { id: 'd2.drive', label: 'Vstupní gain', type: 'range', min: 0, max: 24, step: 0.5, fmt: (v) => '+' + v.toFixed(1) + ' dB' },
    { id: 'trim', label: 'Výstupní trim', type: 'range', min: -24, max: 6, step: 0.5, fmt: (v) => v.toFixed(1) + ' dB', note: 'Zkreslení zvedá hlasitost: gain staging je polovina zvuku.' },
    { id: 'dcBlock', label: 'DC blok', type: 'check', text: 'horní propust 12 Hz na konci' },
  ] },
  { group: 'Obálka hlasitosti', open: false, items: [
    { id: 'env.a', label: 'Attack', type: 'range', ...logMap(0.001, 2), fmt: fS, log: [0.001, 2] },
    { id: 'env.d', label: 'Decay', type: 'range', ...logMap(0.01, 4), fmt: fS, log: [0.01, 4] },
    { id: 'env.s', label: 'Sustain', type: 'range', min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + ' %' },
    { id: 'env.r', label: 'Release', type: 'range', ...logMap(0.01, 4), fmt: fS, log: [0.01, 4] },
  ] },
];
function lfoRate(i) { const l = S.lfo[i]; return l.mode === 'sync' ? syncRateHz(bpm, l.div) : l.hz; }
const curF0 = () => midiToHz(curNote);
let curNote = 28;

// ── UI z specifikace ──────────────────────────────────────────────────────────────────────────────────────────
const controls = [];     // {def, row, input, out}
function buildUI() {
  const host = $('#tzLeft');
  for (const g of SPEC) {
    const d = document.createElement('details');
    d.className = 'card'; d.open = g.open;
    const sm = document.createElement('summary'); sm.textContent = g.group; d.appendChild(sm);
    for (const def of g.items) {
      if (def.sub) { const h = document.createElement('div'); h.className = 'sub'; h.textContent = def.sub; d.appendChild(h); continue; }
      const row = document.createElement('div'); row.className = 'ctl';
      if (def.note && typeof def.note === 'function') { row.innerHTML = '<div class="hint"></div>'; d.appendChild(row); controls.push({ def, row, noteEl: row.firstChild }); continue; }
      const id = 'c_' + def.id.replace(/\./g, '_');
      const lab = document.createElement('label'); lab.htmlFor = id; lab.textContent = def.label; row.appendChild(lab);
      let input, out = null;
      if (def.type === 'range') {
        input = document.createElement('input'); input.type = 'range'; input.min = def.min; input.max = def.max; input.step = def.step;
        out = document.createElement('output'); out.htmlFor = id;
        row.appendChild(input); row.appendChild(out);
      } else if (def.type === 'select') {
        input = document.createElement('select');
        for (const [v, t] of def.opts) { const o = document.createElement('option'); o.value = String(v); o.textContent = t; input.appendChild(o); }
        row.appendChild(input);
      } else {
        const w = document.createElement('label'); w.className = 'chk';
        input = document.createElement('input'); input.type = 'checkbox';
        w.appendChild(input); w.appendChild(document.createTextNode(def.text));
        row.appendChild(w);
      }
      input.id = id;
      if (def.note && typeof def.note === 'string') { const n = document.createElement('div'); n.className = 'hint'; n.textContent = def.note; row.appendChild(n); }
      const c = { def, row, input, out };
      input.addEventListener('input', () => onInput(c));
      controls.push(c); d.appendChild(row);
    }
    host.appendChild(d);
  }
}
function onInput(c) {
  const { def, input } = c;
  let v;
  if (def.type === 'range') v = def.log ? def.to(+input.value) : +input.value;
  else if (def.type === 'select') v = def.num ? +input.value : input.value;
  else v = input.checked;
  setP(def.id, v);
  refresh(); sync();
}
function refresh() {
  for (const c of controls) {
    const { def } = c;
    if (def.show) c.row.hidden = !def.show();
    if (c.noteEl) { c.noteEl.textContent = def.note(); continue; }
    if (def.type === 'range') {
      const v = getP(def.id);
      c.input.value = def.log ? def.from(v) : v;
      c.out.textContent = def.fmt(v);
    } else if (def.type === 'select') c.input.value = String(getP(def.id));
    else c.input.checked = !!getP(def.id);
  }
  $('#tdesc').textContent = TABLE_KINDS[S.table].desc;
}

// ── audio ──────────────────────────────────────────────────────────────────────────────────────────────────────
let ctx = null, node = null, nodes = null;
const tableSent = new Set();
const tables = {};
function ensureTable(i) {
  if (!tables[i]) tables[i] = buildTable(i);
  if (node && !tableSent.has(i)) { node.port.postMessage({ type: 'table', index: i, table: tables[i] }); tableSent.add(i); }
  return tables[i];
}
async function startAudio() {
  const msg = $('#msg');
  try {
    if (!window.AudioContext && !window.webkitAudioContext) throw new Error('Prohlížeč nemá Web Audio.');
    ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
    if (!ctx.audioWorklet) throw new Error('Prohlížeč nemá AudioWorklet (potřebuje Chrome, Edge, Firefox nebo Safari 14.1+ na https nebo localhost).');
    await ctx.audioWorklet.addModule('/trainer-worklet.js');
  } catch (e) { msg.textContent = 'Zvuk se nepodařilo spustit: ' + e.message; return; }
  node = new AudioWorkletNode(ctx, 'trainer', { numberOfInputs: 0, numberOfOutputs: 3, outputChannelCount: [1, 1, 1] });
  const mk = (t, f) => { const n = ctx.createBiquadFilter(); n.type = t; if (f) n.frequency.value = f; return n; };
  const f1 = mk('lowpass', 4000), f2 = mk('peaking', 4000);
  const cutG = ctx.createGain(); cutG.gain.value = 4800;           // ±4 oktávy při hloubce LFO 100 %
  const pre1 = ctx.createGain(), sh1 = ctx.createWaveShaper(), between = mk('peaking', 350);
  const pre2 = ctx.createGain(), sh2 = ctx.createWaveShaper(), trim = ctx.createGain();
  sh1.oversample = sh2.oversample = '4x';
  const drvG = ctx.createGain();
  const dcAn = ctx.createAnalyser(); dcAn.fftSize = 8192;
  const dc = mk('peaking', 12);
  const an = ctx.createAnalyser(); an.fftSize = 16384; an.smoothingTimeConstant = 0.6; an.minDecibels = -120; an.maxDecibels = 0;
  const master = ctx.createGain(); master.gain.value = 0;
  const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -8; comp.knee.value = 6; comp.ratio.value = 12; comp.attack.value = 0.003; comp.release.value = 0.1;
  node.connect(f1, 0); f1.connect(f2); f2.connect(pre1); pre1.connect(sh1); sh1.connect(between); between.connect(pre2); pre2.connect(sh2); sh2.connect(trim);
  node.connect(cutG, 1); cutG.connect(f1.detune); cutG.connect(f2.detune);
  node.connect(drvG, 2); drvG.connect(pre1.gain);
  trim.connect(dcAn); trim.connect(dc); dc.connect(an); an.connect(master); master.connect(comp); comp.connect(ctx.destination);
  nodes = { f1, f2, cutG, pre1, sh1, between, pre2, sh2, trim, drvG, dcAn, dc, an, master };
  bufs = { td: new Float32Array(an.fftSize), fd: new Float32Array(an.frequencyBinCount), dcd: new Float32Array(dcAn.fftSize) };
  ensureTable(S.table);
  curves = {};
  await ctx.resume();
  sync();
  master.gain.setTargetAtTime(10 ** ($('#master').value / 20), ctx.currentTime, 0.1);
  for (const id of ['play', 'latch', 'repeat']) $('#' + id).disabled = false;
  $('#start').textContent = 'Zvuk běží'; $('#start').disabled = true;
  msg.textContent = '';
  requestAnimationFrame(draw);
}
let curves = {};
const curve = (t) => (t === 'off' ? null : (curves[t] ||= distCurve(t)));
const dbToLin = (d) => 10 ** (d / 20);

function sync() {
  if (!node) return;
  const t = ctx.currentTime, set = (p, v) => p.setTargetAtTime(v, t, 0.015);
  ensureTable(S.table);
  node.port.postMessage({ type: 'set', params: {
    table: S.table, wtPos: S.wtPos, level: 1, unison: S.unison, detune: S.detune, phaseMode: S.phaseMode, invert2: S.invert2,
    modRatio: S.modRatio, fmIndex: S.fmIndex, amDepth: S.amDepth, env: { ...S.env },
    lfo: S.lfo.map((l, i) => ({ shape: l.shape, rate: lfoRate(i), depth: l.depth, target: l.target, trigger: l.trigger })),
  } });
  // filtr: key tracking, rezonance (LP/HP: 0–24 dB, BP: Q 0,7–15), druhý filtr jen při 24 dB/okt.
  const f = S.filt, cut = clamp(f.cutoff * (curF0() / F0_REF) ** f.kt, 20, 18000);
  const bp = f.type === 'bandpass';
  for (const n of [nodes.f1, nodes.f2]) {
    const on = n === nodes.f1 || f.slope === 24;
    if (on) { n.type = f.type; n.Q.value = bp ? 0.7 + f.res * 14.3 : f.res * 24; n.gain.value = 0; } else { n.type = 'peaking'; n.gain.value = 0; n.Q.value = 1; }
    set(n.frequency, cut);
  }
  nodes.sh1.curve = curve(S.d1.type); nodes.sh2.curve = curve(S.d2.type);
  const g1 = S.d1.type === 'off' ? 1 : dbToLin(S.d1.drive) / CURVE_RANGE, g2 = S.d2.type === 'off' ? 1 : dbToLin(S.d2.drive) / CURVE_RANGE;
  set(nodes.pre1.gain, g1); set(nodes.pre2.gain, g2);
  nodes.drvG.gain.value = S.d1.type === 'off' ? 0 : 0.8 * g1;     // modulace driveu: ±80 % gainu 1. stupně
  nodes.between.type = S.between ? 'highpass' : 'peaking'; nodes.between.gain.value = 0; nodes.between.Q.value = 0.707;
  set(nodes.trim.gain, dbToLin(S.trim));
  nodes.dc.type = S.dcBlock ? 'highpass' : 'peaking'; nodes.dc.gain.value = 0; nodes.dc.Q.value = 0.707;
}

// ── noty ───────────────────────────────────────────────────────────────────────────────────────────────────────
let held = new Set(), latched = false, repeating = false, repTimer = 0;
const anyOn = () => held.size > 0 || latched || repNoteOn;
let repNoteOn = false;
function noteOn(note) {
  if (!node) return;
  curNote = note;
  node.port.postMessage({ type: 'on', freq: midiToHz(note) });
  sync(); refresh();
}
function noteOff() { if (node) node.port.postMessage({ type: 'off' }); }
function press(key, note) { if (held.has(key)) return; held.add(key); noteOn(note); }
function release(key) { if (!held.delete(key)) return; if (!anyOn()) noteOff(); }
function repLoop() {
  if (!repeating) return;
  const step = 60000 / bpm / 2;
  repNoteOn = true; noteOn(curNote);
  setTimeout(() => { repNoteOn = false; if (!anyOn()) noteOff(); }, step * 0.6);
  repTimer = setTimeout(repLoop, step);
}

// ── kreslení ───────────────────────────────────────────────────────────────────────────────────────────────────
const cv = { scope: $('#scope'), spec: $('#spec'), frame: $('#frame') };
const dims = new Map();                              // rozměry canvasů se čtou z ResizeObserveru, ne z layoutu v každém snímku
const ro = new ResizeObserver((es) => { for (const e of es) dims.set(e.target, [e.contentRect.width, e.contentRect.height]); });
for (const c of Object.values(cv)) ro.observe(c);
function fit(c) {
  const [cw, ch] = dims.get(c) || [c.clientWidth, c.clientHeight], d = Math.min(1.5, devicePixelRatio || 1);
  const w = Math.max(1, Math.round(cw * d)), h = Math.max(1, Math.round(ch * d));
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return [c.getContext('2d'), c.width, c.height, d];
}
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#3eea9a';
let bufs = null, lastHtml = '', lastDraw = 0, lastLive = 0, frameNo = 0, accentAt = -1e9, accentVal = '#3eea9a';
function draw(now) {
  if (!ctx) return;
  requestAnimationFrame(draw);
  const live = anyOn();                              // při hře 30 snímků za sekundu, v klidu 4 (obálka se doznívá ještě 1,5 s)
  if (live) lastLive = now;
  if (now - lastDraw < (live || now - lastLive < 1500 ? 33 : 250)) return;
  lastDraw = now;
  const an = nodes.an, sr = ctx.sampleRate, f0 = curF0();
  const td = bufs.td; an.getFloatTimeDomainData(td);
  const fd = bufs.fd; an.getFloatFrequencyData(fd);
  if (now - accentAt > 2000) { accentVal = css('--sam-green') || '#3eea9a'; accentAt = now; }
  const accent = accentVal;
  // vlna: 3 periody od vzestupného průchodu nulou
  { const [g, W, H] = fit(cv.scope); g.clearRect(0, 0, W, H); g.fillStyle = '#05080a'; g.fillRect(0, 0, W, H);
    g.strokeStyle = 'rgba(255,255,255,.08)'; g.beginPath(); g.moveTo(0, H / 2); g.lineTo(W, H / 2); g.stroke();
    const per = sr / f0, span = Math.min(td.length - 1, Math.round(per * 3));
    let s0 = 0; for (let i = 1; i < td.length - span - 1; i++) { if (td[i - 1] < 0 && td[i] >= 0) { s0 = i; break; } }
    g.strokeStyle = accent; g.lineWidth = 1.5; g.beginPath();
    for (let x = 0; x < W; x++) { const v = td[s0 + Math.floor((x / W) * span)] || 0; const y = H / 2 - clamp(v, -1.2, 1.2) * (H / 2 - 4); x ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke(); }
  // spektrum
  { const [g, W, H, d] = fit(cv.spec); g.fillStyle = '#05080a'; g.fillRect(0, 0, W, H);
    const fx = (f) => (Math.log(f / 20) / Math.log(500)) * W, dbY = (v) => H - clamp((v + 100) / 100, 0, 1) * (H - 14 * d);
    g.font = `${10 * d}px sans-serif`; g.textBaseline = 'top';
    for (let k = 1; k * f0 < 10000; k++) { const x = fx(k * f0); g.strokeStyle = k === 1 ? 'rgba(255,255,255,.28)' : 'rgba(255,255,255,.09)'; g.beginPath(); g.moveTo(x, 12 * d); g.lineTo(x, H); g.stroke(); if (k <= 12) { g.fillStyle = 'rgba(255,255,255,.45)'; g.fillText(k + '×', x + 2, 0); } }
    const cut = S.filt.cutoff * (f0 / F0_REF) ** S.filt.kt; g.setLineDash([4 * d, 4 * d]); g.strokeStyle = '#ffb86b'; g.beginPath(); g.moveTo(fx(clamp(cut, 20, 10000)), 12 * d); g.lineTo(fx(clamp(cut, 20, 10000)), H); g.stroke(); g.setLineDash([]);
    g.fillStyle = '#ffb86b'; g.fillText('cutoff', fx(clamp(cut, 20, 10000)) + 3, 12 * d);
    g.strokeStyle = accent; g.lineWidth = 1.5 * d; g.beginPath();
    const bh = sr / an.fftSize; let first = true;
    for (let x = 0; x < W; x++) { const f1 = 20 * 500 ** (x / W), f2 = 20 * 500 ** ((x + 1) / W); let m = -200; for (let b = Math.max(1, Math.floor(f1 / bh)); b <= Math.max(Math.floor(f1 / bh), Math.floor(f2 / bh)); b++) m = Math.max(m, fd[b] ?? -200); const y = dbY(m); first ? g.moveTo(x, y) : g.lineTo(x, y); first = false; }
    g.stroke(); }
  // snímek wavetable
  { const t = tables[S.table]; const [g, W, H] = fit(cv.frame); g.fillStyle = '#05080a'; g.fillRect(0, 0, W, H);
    if (t) { const ff = S.wtPos * (FRAMES - 1), a = Math.min(FRAMES - 2, Math.floor(ff)), fr = ff - a, m = t.mips[0];
      g.strokeStyle = css('--accent') || accent; g.lineWidth = 1.5; g.beginPath();
      for (let x = 0; x < W; x++) { const i = Math.floor((x / W) * SIZE); const v = m[a * (SIZE + 1) + i] * (1 - fr) + m[(a + 1) * (SIZE + 1) + i] * fr; const y = H / 2 - v * (H / 2 - 4); x ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke(); } }
  if (++frameNo % 5 === 0) {                         // čísla a sloupce stačí aktualizovat zhruba šestkrát za sekundu
  // harmonické
  { const bh = sr / an.fftSize, peak = (k) => { const c = Math.round((k * f0) / bh); let m = -200; for (let b = Math.max(1, c - 2); b <= c + 2; b++) m = Math.max(m, fd[b] ?? -200); return m; };
    const h1 = peak(1), bars = $('#bars'); if (!bars.children.length) for (let k = 1; k <= 8; k++) bars.insertAdjacentHTML('beforeend', `<div><span class="bar"><i></i></span>H${k}<b></b></div>`);
    for (let k = 1; k <= 8; k++) { const el = bars.children[k - 1], v = peak(k) - h1, ok = h1 > -90; el.querySelector('i').style.height = ok ? clamp((v + 60) / 60, 0, 1.2) * 100 + '%' : '0'; el.querySelector('b').textContent = ok ? (k === 1 ? '0 dB' : v.toFixed(0)) : '–'; } }
  // čtení
  { const meanPk = (buf) => { const per = sr / f0, len = buf.length, m = Math.max(1, Math.floor(len / per)) * per | 0, from = len - Math.min(len, m);   // celé periody, jinak neúplná perioda ukazuje falešný offset
      let mean = 0, pk = 0; for (let i = from; i < len; i++) { mean += buf[i]; pk = Math.max(pk, Math.abs(buf[i])); } return [mean / (len - from), pk]; };
    const dcd = bufs.dcd; nodes.dcAn.getFloatTimeDomainData(dcd);
    const [before, pk] = meanPk(dcd), [after] = meanPk(td);
    const html = `<span>f0 <b>${f0.toFixed(1)} Hz</b> (${noteName(curNote)})</span><span>DC před blokem <b class="${Math.abs(before) > 0.02 ? 'warn' : ''}">${before.toFixed(3)}</b></span><span>DC za blokem <b>${after.toFixed(3)}</b></span><span>špička <b class="${pk > 0.98 ? 'warn' : ''}">${pk > 0 ? (20 * Math.log10(pk)).toFixed(1) + ' dBFS' : '–'}</b></span><span>LFO1 <b>${lfoRate(0).toFixed(2)} Hz</b></span><span>LFO2 <b>${lfoRate(1).toFixed(2)} Hz</b></span>`; if (html !== lastHtml) { $('#read').innerHTML = html; lastHtml = html; } }
  }
}

// ── lekce z kánonu ─────────────────────────────────────────────────────────────────────────────────────────────
const A = (h, t) => `<a href="/#${encodeURIComponent(h)}.md">${t}</a>`;
const LESSONS = [
  { id: 'phase', title: 'Fáze reese: dvě pily, které se ruší', src: `${A('20 Basa', '20 Basa')}, kap. 2 (Abis)`, conf: 'naměřeno',
    set: { table: 1, unison: 2, detune: 0, invert2: true, filt: { cutoff: 12000 } },
    body: `<ol><li>Hraj notu: je <b>ticho</b>. Dva stejné hlasy s obrácenou polaritou se vyruší (v Ableton: duplikát clipu + Phase invert).</li><li>Vypni <i>obrátit polaritu</i>: slyšíš plnou pilu.</li><li>Zapni polaritu zpět a posuň <i>Detune</i> na 4 ct: ticho se pomalu otevírá a zavírá. Detune mění fázový rozdíl v čase, takže dostaneš „LFO bez LFO“. (Po vrácení detune na 0 stiskni notu znovu: fáze se nastavuje při každé nové notě, jinak zůstane rozdíl, který už vznikl.)</li><li>Přepni <i>Fázi</i> na náhodnou a hraj notu víckrát: každá zní jinak. Proto reese s <b>random phase 0</b>.</li></ol>` },
  { id: 'filter3', title: 'Filtr na ~3× fundamentu s key trackingem', src: `${A('20 Basa', '20 Basa')}, kap. 2 (Prolix, Restless, Hands Up)`, conf: 'odhad z analýz',
    set: { table: 1, unison: 2, detune: 5, filt: { type: 'bandpass', cutoff: 123.6, res: 0.35, kt: 1 } },
    body: `<ol><li>Pod filtrem čti <i>= 3,00 × f0</i>: pásmová propust sedí na 3. harmonické (123,6 Hz u E1).</li><li>Změň notu (např. A1) při zapnutém key trackingu: filtr jde s notou a poměr zůstane 3×. Vypni key tracking a slyš, jak se zvuk mění.</li><li>V spektru sleduj oranžovou čáru cutoffu proti svislým čárám násobků.</li></ol>`,
    caveat: 'Biquad tady není filtr ze Serum: sklon a rezonance se chovají jinak. Číslo „3×“ je startovní bod odhadnutý z analýz, ne pravidlo.' },
  { id: 'fmbins', title: 'FM biny: N × fundament, ne N půltónů', src: `${A('20 Basa', '20 Basa')}, kap. 2 (Abis; Mefjus, Pythius)`, conf: 'naměřeno',
    set: { table: 0, modRatio: 2, fmIndex: 3 },
    body: `<ol><li>Poměr 2: oktáva, čisté. Poměr 3: kvinta nad oktávou. Poměr 4: dvě oktávy.</li><li>Poměr 5: velká tercie, ale <b>o 14 ct níž</b>. Poměr 7: septima o <b>31 ct níž</b>, ostrá barva. Údaj vidíš pod voličem.</li><li>Zvedej <i>FM index</i> a sleduj, jak ve spektru přibývají pruhy přesně na násobcích f0.</li></ol>`,
    caveat: 'V Serum je „FM“ fázová modulace (PM), tady taky.' },
  { id: 'fmdecay', title: 'FM hodně na začátku, málo na konci', src: `${A('20 Basa', '20 Basa')}, kap. 3 (archetyp 2) a kap. 4 bod 3 (LS, Abis)`, conf: 'naměřeno',
    set: { table: 0, modRatio: 3, fmIndex: 4, env: { a: 0.001, d: 0.05, s: 1, r: 0.15 }, lfo: [{ shape: 'saw', mode: 'sync', div: '1/2', depth: 1, target: 'fm', trigger: true }] },
    body: `<ol><li>Zapni <i>Opakovat notu</i> nebo drž notu: v každém cyklu je zvuk nahoře jasný a postupně se zklidňuje.</li><li>Vypni <i>Trigger</i> u LFO: cyklus se rozjede mimo rytmus not.</li><li>Zkus pilu změnit na sinus: jak se mění charakter pohybu.</li></ol>`,
    caveat: 'Kánon doporučuje obálky na modulátorech (Operator). Trenažér nemá obálku na FM, nahrazuje ji pila LFO v režimu Trigger.' },
  { id: 'amgate', title: 'AM gate 1/16 jako designová volba', src: `${A('20 Basa', '20 Basa')}, kap. 4 bod 6`, conf: 'designová volba, ne změřený standard',
    set: { table: 1, filt: { cutoff: 6000 }, lfo: [{ shape: 'square', mode: 'sync', div: '1/16', depth: 1, target: 'amp', trigger: true }] },
    body: `<ol><li>Při 174 BPM je 1/16 = 11,6 Hz, 1/8 = 5,8 Hz, 1/4 = 2,9 Hz. Přepínej dělení a slyš rytmus.</li><li>Zapni <i>Opakovat notu</i>: s <i>Triggerem</i> hraje gate pokaždé stejně, bez něj se rozejde.</li><li>Sniž hloubku: z gatu je jemný tremolo pohyb.</li></ol>`,
    caveat: 'Že je 1/16 gate u neurofunku standard, se z plných mixů změřit nedá (hi-haty dělají falešné pruhy). Izolované stemy Don\'t Play žádnou 1/16 modulaci neměly. Bereš to jako designovou volbu.' },
  { id: 'twostage', title: 'Dvoustupňová distorze a vstupní gain', src: `${A('20 Basa', '20 Basa')}, kap. 5 (Prolix, Burr Oak, LS 11)`, conf: 'praxe ze zdrojů',
    set: { table: 1, unison: 2, detune: 6, filt: { cutoff: 2500, res: 0.3 }, d1: { type: 'soft', drive: 12 }, between: true, d2: { type: 'hard', drive: 9 }, trim: -9 },
    body: `<ol><li>Vypni 2. stupeň (typ „vypnuto“) a porovnej: bohatší a řízenější struktura, nebo jen hlasitější?</li><li>Zkus jediný ostrý stupeň (Hard clip, +21 dB) proti dvěma stupňům Warm → Hard.</li><li>Sniž <i>Vstupní gain</i> 1. stupně o pár dB: gain před zkreslením je tónový ovladač, ne jen hlasitost.</li><li>Vypni <i>EQ mezi</i>: slyšíš, jak se zkreslení „zmate“ z přebytku spodku (kánon: řez pod 300–400 Hz mezi stupni).</li></ol>`,
    caveat: 'Zdroje píšou „bohatší kontrolovaná struktura“. Sleduj spektrum a poslech, nepřebírej to jako zákon.' },
  { id: 'dc', title: 'DC offset z asymetrického zkreslení', src: `${A('20 Basa', '20 Basa')}, kap. 2 (Abis Grains, Pythius Reese)`, conf: 'praxe ze zdrojů',
    set: { table: 1, d1: { type: 'asym', drive: 14 }, dcBlock: false, trim: -6 },
    body: `<ol><li>Sleduj <b>DC</b> pod spektrem a posun křivky na vlně: asymetrické zkreslení ji posune mimo nulu.</li><li>Zapni <i>DC blok</i>: DC zmizí.</li><li>Přepni zkreslení na Soft clip: DC téměř není, protože tvar je symetrický.</li></ol>`,
    caveat: 'DC se neslyší, ale bere headroom a kazí sub i limiter. Proto blok na konci řetězu.' },
  { id: 'third', title: 'Silná 3. harmonická', src: `${A('20 Basa', '20 Basa')}, kap. 2 (Prolix, 5,66×)`, conf: 'naměřeno (u hotové stopy)',
    set: { table: 4, wtPos: 0.7, filt: { cutoff: 12000 } },
    body: `<ol><li>Sleduj sloupce harmonických: H3 proti H1 v dB. Posouvej <i>Pozici</i> tabulky 0 až 1.</li><li>Vrať pozici na 0, vyber Pilu a zapni asymetrické zkreslení: H3 a sudé harmonické vyrostou jinou cestou.</li></ol>`,
    caveat: 'Číslo 5,66× je změřené u konkrétní hotové stopy po těžkém zkreslení. Trenažér ukazuje stejný druh efektu, ne stejné číslo.' },
  { id: 'wtlfo', title: 'Pohyb pozicí tabulky (formant), LFO v režimu Trigger', src: `${A('20 Basa', '20 Basa')}, kap. 3 (archetyp 7) a kap. 4 bod 2 (Pythius, Don't Play)`, conf: 'naměřeno (řeč)',
    set: { table: 3, wtPos: 0.1, unison: 2, detune: 5, filt: { cutoff: 3500, res: 0.2 }, lfo: [{ shape: 'saw', mode: 'sync', div: '1/4', depth: 0.7, target: 'wt', trigger: true }] },
    body: `<ol><li>Zapni <i>Opakovat notu</i>: každá nota začíná stejným spektrálním tvarem (Trigger).</li><li>Vypni <i>Trigger</i>: tvar se vůči notám posouvá a zvuk se mění z noty na notu.</li><li>Sleduj spektrum: hrb formantu putuje harmonickými.</li></ol>` },
  { id: 'sub', title: 'Čistý sub: sinus, mono, nic víc', src: `${A('20 Basa', '20 Basa')}, kap. 7`, conf: 'naměřeno',
    set: { table: 0, filt: { cutoff: 150 }, env: { a: 0.005, d: 0.1, s: 1, r: 0.1 } },
    body: `<ol><li>Spektrum má jedinou čáru na f0. U reálných sub stop je H2 hluboko pod hlavním tónem.</li><li>Zapni asymetrické zkreslení: harmonické vzniknou v řetězu. Kánon radí tvořit je <b>v synthu</b> (FM ze sinu), ne distorzí v řetězu.</li><li>Ve sluchátkách si poslech zkontroluj: 41 Hz většina repro nezahraje.</li></ol>` },
];
let curLesson = null;
function showLesson(l) {
  curLesson = l.id;
  S = merge(DEFAULT(), JSON.parse(JSON.stringify(l.set)));
  $('#lesson').innerHTML = `<h3>${l.title}</h3><div class="src">${l.src} · <span class="tagc ${l.conf.startsWith('naměř') || l.conf.startsWith('praxe') ? '' : 'dash'}">${l.conf}</span></div>${l.body}${l.caveat ? `<div class="caveat">${l.caveat}</div>` : ''}<div class="src">Nastavení je načtené. Stiskni <b>Hrát</b>${node ? '' : ' (nejdřív Zapnout zvuk)'}.</div>`;
  for (const b of document.querySelectorAll('#lessons button')) b.setAttribute('aria-current', String(b.dataset.id === l.id));
  refresh(); sync();
  if (anyOn()) noteOn(curNote);                       // držená nota se spustí znovu, aby měly hlasy čerstvou fázi
}
function buildLessons() {
  const host = $('#lessons');
  for (const l of LESSONS) {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.id = l.id; b.setAttribute('aria-current', 'false');
    b.innerHTML = `${l.title}<small>${l.conf}</small>`;
    b.addEventListener('click', () => showLesson(l));
    host.appendChild(b);
  }
}

// ── události ───────────────────────────────────────────────────────────────────────────────────────────────────
function wire() {
  const rootSel = $('#root');
  for (let n = 24; n <= 48; n++) { const o = document.createElement('option'); o.value = n; o.textContent = `${noteName(n)} (${midiToHz(n).toFixed(1)} Hz)`; if (n === 28) o.selected = true; rootSel.appendChild(o); }
  rootSel.addEventListener('change', () => { rootNote = +rootSel.value; curNote = rootNote; sync(); refresh(); });
  $('#bpm').addEventListener('input', (e) => { bpm = clamp(+e.target.value || 174, 60, 220); sync(); refresh(); });
  $('#master').addEventListener('input', (e) => { $('#masterOut').textContent = e.target.value.replace('-', '−') + ' dB'; if (nodes) nodes.master.gain.setTargetAtTime(10 ** (e.target.value / 20), ctx.currentTime, 0.05); });
  $('#start').addEventListener('click', startAudio);
  const play = $('#play');
  const down = () => { play.setAttribute('aria-pressed', 'true'); press('btn', rootNote); };
  const up = () => { play.setAttribute('aria-pressed', 'false'); release('btn'); };
  play.addEventListener('pointerdown', (e) => { e.preventDefault(); down(); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) play.addEventListener(ev, up);
  play.addEventListener('keydown', (e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); down(); } });
  play.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); up(); } });
  $('#latch').addEventListener('click', (e) => { latched = !latched; e.currentTarget.setAttribute('aria-pressed', String(latched)); if (latched) noteOn(rootNote); else if (!anyOn()) noteOff(); });
  $('#repeat').addEventListener('click', (e) => { repeating = !repeating; e.currentTarget.setAttribute('aria-pressed', String(repeating)); clearTimeout(repTimer); if (repeating) repLoop(); });
  const KEYS = 'zsxdcvgbhnjm';
  addEventListener('keydown', (e) => {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target; if (t && (t.tagName === 'INPUT' && t.type === 'number' || t.tagName === 'TEXTAREA')) return;
    const i = KEYS.indexOf(e.key.toLowerCase()); if (i >= 0) press(e.key.toLowerCase(), rootNote + i);
  });
  addEventListener('keyup', (e) => { const i = KEYS.indexOf(e.key.toLowerCase()); if (i >= 0) release(e.key.toLowerCase()); });
  addEventListener('blur', () => { held.clear(); if (!anyOn()) noteOff(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { held.clear(); latched = false; repeating = false; $('#latch').setAttribute('aria-pressed', 'false'); $('#repeat').setAttribute('aria-pressed', 'false'); noteOff(); } });
  const sk = $('#skin');                                    // vzhled sdílený s ostatními stránkami (localStorage vault.skin)
  if (sk) {
    const get = () => { try { return JSON.parse(localStorage.getItem('vault.skin')) || 'samurai'; } catch { return 'samurai'; } };
    sk.value = get();
    sk.addEventListener('change', () => { try { localStorage.setItem('vault.skin', JSON.stringify(sk.value)); } catch { /* soukromý režim */ } document.documentElement.dataset.theme = sk.value; });
  }
}

buildUI(); buildLessons(); wire(); refresh();
