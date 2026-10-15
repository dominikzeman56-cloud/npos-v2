// Presety: master–detail browser for the compact preset index (presets.json / /api/presets) + build detail.
'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lsGet = (k, d) => { try { const v = localStorage.getItem('vault.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('vault.' + k, JSON.stringify(v)); } catch { /* private mode */ } };
const isNarrow = () => matchMedia('(max-width: 899px)').matches;

const BASA = '/#' + encodeURIComponent('20 Basa.md') + '::' + encodeURIComponent('3. Archetypy basů');
const ARCH = {
  'detuned-unison-reese': ['fázový reese (detune)', 'seed, archetyp 1'],
  'fm-distorted-body': ['FM + distorze', 'seed, archetyp 2'],
  'clean-sub-sine': ['čistý sub', 'seed, archetyp 5'],
  'osc-warp-body': ['tělo z warpu jiným oscilátorem', 'kandidát, archetyp 16'],
  'unclassified': ['nezařazeno', ''],
};
const FN = { sub: 'sub', body: 'tělo (body)', movement: 'pohyb', noise: 'šum', texture: 'textura', lead: 'lead', pad: 'pad', fx: 'FX', other: 'jiné' };
const WARP = { kPD_OSC: 'PD z osc', kPD_OSC2: 'PD z osc (2)', kPD_NOISE: 'PD ze šumu', kSync: 'Sync', kFM_OSC: 'FM z osc', kFM_OSC2: 'FM z osc (2)',
  kFM_SUB: 'FM ze subu', kFM_NOISE: 'FM ze šumu', kAM_OSC: 'AM z osc', kRM_OSC: 'RM z osc', kRM_OSC2: 'RM z osc (2)' };
const warpName = (w) => WARP[w] || w.replace(/^k/, '');
const uniBucket = (n) => (n <= 1 ? '1' : n <= 4 ? '2-4' : '5+');

let DATA = { packs: [], presets: [] };
let SEL = null;
const BUILDS = new Map();
const F = { q: '', pack: '', xw: '', uni: '', mono: '', fn: new Set(), arch: new Set() };

/* ---------- URL state ---------- */
function readUrl() {
  const u = new URLSearchParams(location.search);
  F.q = u.get('q') || ''; F.pack = u.get('pack') || ''; F.xw = u.get('xw') || ''; F.uni = u.get('uni') || ''; F.mono = u.get('mono') || '';
  F.fn = new Set((u.get('fn') || '').split(',').filter(Boolean));
  F.arch = new Set((u.get('arch') || '').split(',').filter(Boolean));
  SEL = u.get('id') || null;
}
function urlFor() {
  const u = new URLSearchParams();
  for (const k of ['q', 'pack', 'xw', 'uni', 'mono']) if (F[k]) u.set(k, F[k]);
  if (F.fn.size) u.set('fn', [...F.fn].join(','));
  if (F.arch.size) u.set('arch', [...F.arch].join(','));
  if (SEL) u.set('id', SEL);
  const s = u.toString();
  return location.pathname + (s ? '?' + s : '');
}

/* ---------- filters ---------- */
// one predicate per facet, so each facet can count "what would match if only my own choice changed"
const TESTS = {
  q: (p) => !F.q || p.name.toLowerCase().includes(F.q.toLowerCase()),
  pack: (p) => !F.pack || p.source_id === F.pack,
  xw: (p) => !F.xw || (F.xw === 'any' ? p.cues.cross_warp.length > 0 : F.xw === 'none' ? p.cues.cross_warp.length === 0 : p.cues.cross_warp.includes(F.xw)),
  uni: (p) => !F.uni || uniBucket(p.cues.max_unison) === F.uni,
  mono: (p) => !F.mono || (F.mono === 'mono') === !!p.cues.mono,
  fn: (p) => !F.fn.size || F.fn.has(p.function),
  arch: (p) => !F.arch.size || F.arch.has(p.archetype),
};
const passes = (p, skip) => Object.entries(TESTS).every(([k, t]) => k === skip || t(p));
function countBy(skip, key) {
  const m = new Map();
  for (const p of DATA.presets) if (passes(p, skip)) for (const v of [].concat(key(p))) m.set(v, (m.get(v) || 0) + 1);
  return m;
}
function fillSelect(el, skip, opts) {
  el.innerHTML = opts.map(([v, label, n]) => `<option value="${esc(v)}"${F[skip] === v ? ' selected' : ''}>${esc(label)}${n != null ? ` (${n})` : ''}</option>`).join('');
}
function renderFacets() {
  const pk = countBy('pack', (p) => p.source_id);
  fillSelect($('#pack'), 'pack', [['', 'všechny packy'], ...DATA.packs.map((x) => [x.id, x.title, pk.get(x.id) || 0])]);
  const xw = countBy('xw', (p) => p.cues.cross_warp);
  const xwAny = countBy('xw', (p) => (p.cues.cross_warp.length ? 'any' : 'none'));
  fillSelect($('#xw'), 'xw', [['', 'vše'], ['any', 'jakýkoli cross-warp', xwAny.get('any') || 0], ['none', 'bez cross-warpu', xwAny.get('none') || 0],
    ...[...xw].sort((a, b) => b[1] - a[1]).map(([w, n]) => [w, warpName(w), n])]);
  const un = countBy('uni', (p) => uniBucket(p.cues.max_unison));
  fillSelect($('#uni'), 'uni', [['', 'vše'], ['1', '1 hlas', un.get('1') || 0], ['2-4', '2–4 hlasy', un.get('2-4') || 0], ['5+', '5 a víc', un.get('5+') || 0]]);
  const mo = countBy('mono', (p) => (p.cues.mono ? 'mono' : 'poly'));
  fillSelect($('#mono'), 'mono', [['', 'vše'], ['mono', 'mono', mo.get('mono') || 0], ['poly', 'poly', mo.get('poly') || 0]]);
  const fn = countBy('fn', (p) => p.function);
  $('#fn').innerHTML = Object.keys(FN).filter((k) => fn.has(k) || F.fn.has(k))
    .map((k) => `<button type="button" class="chip${F.fn.has(k) ? ' on' : ''}" data-fn="${k}" aria-pressed="${F.fn.has(k)}">${esc(FN[k])}<span class="n">${fn.get(k) || 0}</span></button>`).join('');
  const ar = countBy('arch', (p) => p.archetype);
  $('#arch').innerHTML = [...new Set([...Object.keys(ARCH), ...ar.keys()])].filter((k) => ar.has(k) || F.arch.has(k))
    .map((k) => `<button type="button" class="chip${F.arch.has(k) ? ' on' : ''}" data-arch="${esc(k)}" aria-pressed="${F.arch.has(k)}" title="${esc(ARCH[k]?.[0] || '')}">${esc(k)}<span class="n">${ar.get(k) || 0}</span></button>`).join('');
}

/* ---------- formatting ---------- */
const f2 = (v) => (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 100) / 100);
const dflt = '<span class="dim">výchozí</span>';
const val = (v, fmt = f2) => (v == null ? dflt : fmt(v));
const bar = (v) => (v == null ? '' : `<i class="bar"><b style="width:${Math.max(0, Math.min(100, v * 100))}%"></b></i>`);
const kind = (k) => (k ? k.replace(/Osc$/, '').replace('MultiSample', 'Multisample') : '');
const FXN = { FXDistortion: 'Distortion', FXFilter: 'Filter', FXEQ: 'EQ', FXComp: 'Comp', FXReverb: 'Reverb', FXHyperD: 'Hyper/Dimension', FXChorus: 'Chorus',
  FXPhaser: 'Phaser', FXFlanger: 'Flanger', FXDelay: 'Delay', FXUtils: 'Utility', FXConv: 'Convolve', FXBode: 'Bode', FXSplit: 'Split' };
const KEYP = ['Drive', 'Freq', 'Reso', 'Wet', 'Thresh', 'Ratio', 'Makeup', 'Rate', 'Depth', 'Feedback', 'Size', 'Decay', 'Gain1', 'Freq1', 'Gain2', 'Freq2', 'Width', 'Shift'];

const archTag = (p) => {
  if (p.archetype === 'unclassified') return '<span class="tag">nezařazeno</span>';
  const a = ARCH[p.archetype];
  return `<a class="tag arch" href="${BASA}" title="${esc(a ? a[0] + ' (' + a[1] + ')' : '')} – otevře tabulku archetypů">${esc(p.archetype)} ↗</a>`;
};
function cueList(p) {
  const c = p.cues;
  return [
    `wavetable osc ${c.active_osc}`, c.noise ? 'noise' : null, c.sub ? 'sub' : null,
    `unison ${c.max_unison}`,
    c.cross_warp.length ? c.cross_warp.map(warpName).join(', ') : null,
    c.silent_mod_osc ? `tichý modulátor ×${c.silent_mod_osc}` : null,
    c.fine_spread ? 'rozladění Fine' : null,
    c.lfo_to_filter ? 'LFO → filtr' : null,
    c.mono ? 'mono' : 'poly',
    `FX ${c.fx_count}`,
  ].filter(Boolean);
}

/* ---------- list ---------- */
function rowHtml(p) {
  const c = p.cues;
  const bits = [c.cross_warp.length ? c.cross_warp.map(warpName).join(', ') : null, c.max_unison > 1 ? `unison ${c.max_unison}` : null, c.mono ? 'mono' : null].filter(Boolean).join(' · ');
  const arch = p.archetype === 'unclassified' ? '' : `<span class="tag" style="background:var(--accent-bg);color:var(--link)">${esc(p.archetype)}</span>`;
  return `<button type="button" class="row" data-id="${esc(p.id)}" aria-current="${p.id === SEL}">
    <span class="nm">${esc(p.name)}</span>
    <span class="mt"><span class="tag">${esc(FN[p.function] || p.function)}</span>${arch}${bits ? `<span>${esc(bits)}</span>` : ''}</span></button>`;
}
function renderList() {
  const list = DATA.presets.filter((p) => passes(p)).sort((a, b) => a.name.localeCompare(b.name, 'cs'));
  const shown = list.slice(0, 500);
  $('#list').innerHTML = shown.length ? shown.map(rowHtml).join('') : '<div class="pempty">Nic neodpovídá filtrům.</div>';
  const active = ['q', 'pack', 'xw', 'uni', 'mono'].filter((k) => F[k]).length + F.fn.size + F.arch.size;
  const extra = ['pack', 'xw', 'uni', 'mono'].filter((k) => F[k]).length;
  $('#count').textContent = `${list.length} z ${DATA.presets.length} presetů` + (list.length > shown.length ? ` (zobrazeno ${shown.length})` : '');
  $('#fsum').textContent = extra ? `${extra} aktivní` : '';
  $('#reset').hidden = !active;
  return list;
}

/* ---------- detail ---------- */
/* ---------- synth panel: knobs, LEDs, LCD, signal flow ---------- */
// Knob positions use the ranges seen in the files (normalized 0–1, percent 0–100, ±100 for mod amounts). Orientation only:
// units are not verified against the Serum UI, so every knob also prints the stored number.
const A0 = -135, SWEEP = 270; // degrees, 0 = 12 o'clock
const pt = (r, deg) => [24 + r * Math.sin(deg * Math.PI / 180), 24 - r * Math.cos(deg * Math.PI / 180)];
function arc(r, from, to) {
  if (Math.abs(to - from) < 0.5) return '';
  const [x1, y1] = pt(r, from), [x2, y2] = pt(r, to);
  return `<path d="M${x1.toFixed(2)} ${y1.toFixed(2)}A${r} ${r} 0 ${Math.abs(to - from) > 180 ? 1 : 0} ${to > from ? 1 : 0} ${x2.toFixed(2)} ${y2.toFixed(2)}"/>`;
}
// opts: min, max, bipolar, text (override readout), steps
function knob(label, v, { min = 0, max = 1, bipolar = false, text } = {}) {
  const has = v != null && Number.isFinite(v);
  const t = has ? Math.max(0, Math.min(1, (v - min) / (max - min))) : null;
  let val = '', ptr = '';
  if (has) {
    const ang = A0 + SWEEP * t;
    val = bipolar ? arc(17, 0, ang) : arc(17, A0, ang);
    const [px1, py1] = pt(6, ang), [px2, py2] = pt(13, ang);
    ptr = `<line x1="${px1.toFixed(1)}" y1="${py1.toFixed(1)}" x2="${px2.toFixed(1)}" y2="${py2.toFixed(1)}"/>`;
  }
  const shown = text != null ? text : has ? f2(v) : 'výchozí';
  return `<div class="kn${has ? '' : ' nov'}"><svg viewBox="0 0 48 48" aria-hidden="true">
      <g class="trk">${arc(17, A0, A0 + SWEEP)}</g><g class="val">${val}</g><g class="ptr">${ptr}</g>${bipolar ? '<circle class="mid" cx="24" cy="7" r="1.3"/>' : ''}</svg>
    <b>${esc(label)}</b><i>${esc(String(shown))}</i></div>`;
}
const led = (on) => `<span class="led${on ? ' on' : ''}" title="${on ? 'zapnuto' : 'vypnuto'}"></span>`;
const lcd = (s, sub) => `<div class="lcd"><span>${esc(s || '—')}</span>${sub ? `<small>${esc(sub)}</small>` : ''}</div>`;
const mod = (title, on, body, cls = '') => `<section class="mod ${cls}${on ? '' : ' off'}"><header>${led(on)}<h4>${esc(title)}</h4></header>${body}</section>`;
const readout = (k, v) => `<div class="ro"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`;

function oscModule(o, slot) {
  const name = ['OSC A', 'OSC B', 'OSC C'][slot];
  if (!o) return mod(name, slot === 0, lcd('výchozí', 'v souboru nic neuloženo'));
  const w1 = o.warp ? warpName(o.warp) + (o.warp_amt != null ? ' · ' + f2(o.warp_amt) : '') : '';
  const w2 = o.warp2 ? warpName(o.warp2) + (o.warp2_amt != null ? ' · ' + f2(o.warp2_amt) : '') : '';
  const screen = lcd([kind(o.kind), o.table].filter(Boolean).join(' · ') || 'wavetable', [w1, w2].filter(Boolean).join('  ＋  ') || 'bez warpu');
  const knobs = [
    knob('OCT', o.octave, { min: -4, max: 4, bipolar: true }),
    o.pitch != null ? knob('SEMI', o.pitch, { min: -12, max: 12, bipolar: true }) : '',
    o.fine != null ? knob('FINE', o.fine, { min: -100, max: 100, bipolar: true }) : '',
    knob('LEVEL', o.level),
    knob('UNI', o.unison, { min: 1, max: 16, text: String(o.unison) }),
    knob('DETUNE', o.detune),
    o.pan != null ? knob('PAN', o.pan, { min: -1, max: 1, bipolar: true }) : '',
  ].join('');
  return mod(name, o.enabled, screen + `<div class="knobs">${knobs}</div>`);
}
function noiseModule(x) {
  return mod('NOISE', x.enabled, lcd('šum', 'bez wavetable') + `<div class="knobs">${knob('LEVEL', x.level)}${x.pan != null ? knob('PAN', x.pan, { min: -1, max: 1, bipolar: true }) : ''}${x.pitch_track != null ? readout('PITCH TRACK', f2(x.pitch_track)) : ''}</div>`, 'small');
}
function subModule(x) {
  return mod('SUB', x.enabled, lcd('sinus', 'podtón pod oscilátory') + `<div class="knobs">${knob('LEVEL', x.level)}${knob('OCT', x.octave, { min: -4, max: 4, bipolar: true })}${x.coarse != null ? knob('COARSE', x.coarse, { min: -12, max: 12, bipolar: true }) : ''}${x.pan != null ? knob('PAN', x.pan, { min: -1, max: 1, bipolar: true }) : ''}</div>`, 'small');
}
function filterModule(f) {
  const knobs = [knob('CUTOFF', f.freq), knob('RESO', f.reso, { max: 100 }), knob('DRIVE', f.drive, { max: 100 }), f.wet != null ? knob('MIX', f.wet, { max: 100 }) : ''].join('');
  return mod(`FILTR ${f.slot + 1}`, f.on, lcd(f.type || 'výchozí typ') + `<div class="knobs">${knobs}</div>`, 'small');
}
function fxModule(e, i) {
  const keys = Object.entries(e.params).filter(([k]) => KEYP.some((x) => k.endsWith(x))).slice(0, 4);
  const knobs = keys.map(([k, v]) => {
    const n = k.replace(/^kParam/, '');
    return /^(Wet|Drive)$/.test(n) ? knob(n.toUpperCase(), v, { max: 100 }) : readout(n.toUpperCase(), f2(v));
  }).join('');
  return `<div class="slot"><span class="no">${i + 1}</span>${mod(FXN[e.module] || e.module, e.on, (e.mode ? lcd(String(e.mode).replace(/^k/, '')) : '') + (knobs ? `<div class="knobs">${knobs}</div>` : '<div class="dim" style="font-size:12px">bez nastavených parametrů</div>'), 'fx')}</div>`;
}
function modMatrix(b) {
  const rows = b.modulation.map((m) => {
    const t = Math.max(-1, Math.min(1, m.amount / 100));
    const fill = t >= 0 ? `left:50%;width:${(t * 50).toFixed(1)}%` : `left:${(50 + t * 50).toFixed(1)}%;width:${(-t * 50).toFixed(1)}%`;
    return `<div class="mrow"><span class="src">${esc(m.source)}</span><span class="arr">→</span><span class="dst">${esc(m.dest)} <em>${esc(m.param)}</em></span>
      <span class="amt"><i class="bip"><b style="${fill}"></b></i><u>${f2(m.amount)}</u></span></div>`;
  }).join('');
  return rows || '<div class="dim">matice je prázdná</div>';
}
function renderBuild(b) {
  const flow = ['OSC', 'FILTR', 'FX', 'OUT'].map((s, i) => `<span>${s}</span>${i < 3 ? '<em>▶</em>' : ''}`).join('');
  const oscs = [0, 1, 2].map((s) => oscModule(b.oscillators.find((o) => o.slot === s), s)).join('');
  const flt = b.filters.length ? b.filters.map(filterModule).join('') : mod('FILTR', false, lcd('bez filtru'), 'small');
  const aux = noiseModule(b.noise) + subModule(b.sub) + flt;
  const fx = b.fx.length ? `<div class="chain">${b.fx.map(fxModule).join('')}</div>` : '<div class="dim">bez FX</div>';
  const lfo = b.lfos.map((l) => `<span class="pill">LFO ${l.index + 1} · ${esc(l.type || l.mode || 'výchozí')}${l.rate != null ? ' · rate ' + f2(l.rate) : ''}${l.points ? ' · ' + l.points + ' bodů' : ''}</span>`).join('');
  const macros = b.macros.length ? `<div class="macros">${b.macros.map((m) => knob('M' + (m.index + 1), m.value, { max: 100 })).join('')}</div>` : '';
  const v = b.voice;
  const voice = `<div class="voice">${led(v.kParamMonoToggle === 1)}<b>MONO</b>${led(v.kParamLegato === 1)}<b>LEGATO</b>${v.kParamPortamentoTime != null ? `<b>PORTA</b><i>${f2(v.kParamPortamentoTime)}</i>` : ''}</div>`;
  return `<div class="panel">
    <div class="flow" aria-label="Signálový tok">${flow}</div>
    <div class="sect"><h3>Oscilátory</h3><div class="g-osc">${oscs}</div></div>
    <div class="sect"><h3>Noise, sub, filtry a hlas</h3><div class="g-aux">${aux}${mod('HLAS', true, voice, 'small')}</div></div>
    <div class="sect"><h3>FX řetěz</h3>${fx}</div>
    <div class="sect"><h3>Modulace</h3><div class="matrix">${modMatrix(b)}</div>${lfo ? `<div class="pills">${lfo}</div>` : ''}${macros}</div>
  </div>
  <div class="pnote">Serum 2 má tři wavetable oscilátory (A–C) a k nim Noise a Sub; v souboru se jmenují <code>NoiseOsc3</code> a <code>SubOsc4</code>. Čísla pod knoby jsou přímo ze souboru (normalizované, jednotky neověřené proti Serum UI); poloha knobu je jen orientační. „výchozí“ = v souboru chybí. Zdroje modulace mimo LFO, obálky a makra zatím nejsou pojmenované.</div>`;
}
async function loadBuildFor(id) {
  if (BUILDS.has(id)) return BUILDS.get(id);
  let out = null;
  for (const url of [`/api/preset?id=${encodeURIComponent(id)}`, `/data/builds/${encodeURIComponent(id)}.json`]) {
    try { const r = await fetch(url); if (r.ok && (r.headers.get('content-type') || '').includes('json')) { out = await r.json(); break; } } catch { /* next */ }
  }
  BUILDS.set(id, out);
  return out;
}
async function renderDetail() {
  const el = $('#detail');
  const p = DATA.presets.find((x) => x.id === SEL);
  if (!p) { el.innerHTML = '<div class="pick">Vyber preset ze seznamu.</div>'; return; }
  const head = `<button class="back-list" type="button" id="backlist">← Seznam</button>
    <div class="dh"><h2>${esc(p.name)}</h2>
      <div class="l"><div class="tags"><span class="tag">${esc(FN[p.function] || p.function)}</span>${archTag(p)}<span class="tag hyp" title="Funkce a archetyp jsou návrh z heuristiky (jméno + stopy v souboru)">hypotéza</span></div>
        <div class="cues">${cueList(p).map(esc).join(' <span class="dim">·</span> ')}</div></div>
      <div class="r">${(p.why || []).length ? `<div class="why">Proč tenhle návrh: ${esc(p.why.join('; '))}</div>` : ''}
        <div class="meta">${esc(p.synth || '')}${(p.tags || []).length ? ' · tagy ve Seru: ' + esc(p.tags.join(', ')) : ''}</div></div></div>`;
  el.innerHTML = head + '<div id="bd" class="dim">Načítám stavbu…</div>';
  $('#backlist').onclick = () => { history.length > 1 ? history.back() : select(null, false); };
  const myId = SEL;
  const b = await loadBuildFor(myId);
  if (SEL !== myId) return; // user moved on
  $('#bd').className = '';
  $('#bd').innerHTML = b ? renderBuild(b)
    : '<div class="dim">Stavba presetu tu není k dispozici (je jen v lokálním režimu, <code>node server.mjs</code>).</div>'
      + '<div class="sec"><h3>FX řetěz</h3>' + ((p.fx_chain || []).length ? `<ol class="fxl">${p.fx_chain.map((x) => `<li>${esc(x)}</li>`).join('')}</ol>` : '<div class="dim">bez FX</div>') + '</div>';
}

/* ---------- selection / render ---------- */
function applySelectionUi() {
  $('#pzmain').classList.toggle('show-detail', !!SEL && isNarrow());
  for (const r of document.querySelectorAll('.row')) r.setAttribute('aria-current', String(r.dataset.id === SEL));
}
function select(id, push = true) {
  SEL = id;
  if (push) history.pushState(null, '', urlFor()); else history.replaceState(null, '', urlFor());
  applySelectionUi(); renderDetail();
  if (id) scrollTo({ top: 0, behavior: 'instant' });
}
function render() {
  renderFacets();
  const list = renderList();
  if (!SEL && !isNarrow() && list[0]) SEL = list[0].id; // desktop: always show a detail
  history.replaceState(null, '', urlFor());
  applySelectionUi();
}

function bind() {
  $('#q').value = F.q;
  $('#q').addEventListener('input', (e) => { F.q = e.target.value.trim(); render(); });
  for (const k of ['pack', 'xw', 'uni', 'mono']) $('#' + k).addEventListener('change', (e) => { F[k] = e.target.value; render(); });
  $('#fn').addEventListener('click', (e) => { const b = e.target.closest('[data-fn]'); if (!b) return; const k = b.dataset.fn; F.fn.has(k) ? F.fn.delete(k) : F.fn.add(k); render(); });
  $('#arch').addEventListener('click', (e) => { const b = e.target.closest('[data-arch]'); if (!b) return; const k = b.dataset.arch; F.arch.has(k) ? F.arch.delete(k) : F.arch.add(k); render(); });
  $('#list').addEventListener('click', (e) => { const r = e.target.closest('.row'); if (r) select(r.dataset.id); });
  $('#reset').addEventListener('click', () => { Object.assign(F, { q: '', pack: '', xw: '', uni: '', mono: '', fn: new Set(), arch: new Set() }); $('#q').value = ''; render(); });
  const sk = $('#skin'); sk.value = lsGet('skin', 'samurai'); // skin switcher (shared with the vault: localStorage vault.skin)
  sk.addEventListener('change', () => { lsSet('skin', sk.value); applyTheme(); });
  $('#filters').open = ['pack', 'xw', 'uni', 'mono'].some((k) => F[k]); // collapsed unless one of them is set
  addEventListener('popstate', () => { readUrl(); $('#q').value = F.q; render(); renderDetail(); });
  matchMedia('(max-width: 899px)').addEventListener('change', () => { if (!SEL && !isNarrow()) render(); applySelectionUi(); });
}
function applyTheme() {
  const t = lsGet('skin', 'samurai');
  document.documentElement.dataset.theme = t;
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', ({ light: '#ffffff', samurai: '#0b0f14' })[t] || '#1e1e1e');
}
async function load() {
  for (const url of ['/data/presets.json', '/api/presets']) {
    try { const r = await fetch(url); if (r.ok && (r.headers.get('content-type') || '').includes('json')) return r.json(); } catch { /* try next */ }
  }
  throw new Error('index presetů nenalezen');
}

(async () => {
  applyTheme(); readUrl(); bind();
  try { DATA = await load(); } catch (e) { $('#intro').textContent = 'Chyba: ' + e.message; return; }
  const arch = DATA.presets.reduce((m, p) => (m[p.archetype] = (m[p.archetype] || 0) + 1, m), {});
  $('#intro').innerHTML = `<b>${DATA.presets.length} presetů</b> z ${DATA.packs.length} packů, přečtených přímo ze souborů <code>.SerumPreset</code>. `
    + `Stavba (oscilátory, filtry, FX, modulace) je ze souboru; <b>funkce a archetyp jsou návrh</b> z heuristiky se štítkem hypotéza, dokud je neověří poslech nebo A/B v Serumu. `
    + `Nejčastější návrh: ${Object.entries(arch).filter(([k]) => k !== 'unclassified').sort((a, b) => b[1] - a[1]).map(([k, n]) => `${esc(k)} ${n}`).join(' · ')}.`;
  $('#legend').innerHTML = '<b>Archetypy</b> (odkaz otevře tabulku v <a href="' + BASA + '">20 Basa → 3. Archetypy basů</a>): '
    + Object.entries(ARCH).filter(([k]) => k !== 'unclassified').map(([k, [d, s]]) => `<code>${esc(k)}</code> = ${esc(d)} (${esc(s)})`).join(' · ')
    + '. Cross-warp = warp slyšitelného oscilátoru řízený jiným oscilátorem (PD, FM, AM, RM, Sync). Tichý modulátor = zapnutý oscilátor s hlasitostí 0 bez modulace hlasitosti. '
    + 'Serum 2 má tři wavetable oscilátory (A–C) plus Noise a Sub.';
  render();
  renderDetail();
})();
