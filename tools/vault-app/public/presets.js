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
  $('#count').textContent = `${list.length} z ${DATA.presets.length} presetů` + (list.length > shown.length ? ` (zobrazeno ${shown.length})` : '');
  $('#fsum').textContent = active ? `${active} aktivní` : '';
  $('#reset').hidden = !active;
  return list;
}

/* ---------- detail ---------- */
function oscCard(o, slot) {
  const names = ['OSC A', 'OSC B', 'OSC C'];
  if (!o) return `<div class="osc off"><div class="oh"><b>${names[slot]}</b><span class="st">${slot === 0 ? 'výchozí' : 'vypnuto'}</span></div><div class="wt">v souboru nic neuloženo</div></div>`;
  const wt = [kind(o.kind), o.table].filter(Boolean).join(' · ');
  const w1 = o.warp ? warpName(o.warp) + (o.warp_amt != null ? ' ' + f2(o.warp_amt) : '') : '';
  const w2 = o.warp2 ? warpName(o.warp2) + (o.warp2_amt != null ? ' ' + f2(o.warp2_amt) : '') : '';
  const warp = [w1, w2].filter(Boolean).join(' + ');
  return `<div class="osc${o.enabled ? '' : ' off'}">
    <div class="oh"><b>${names[slot]}</b><span class="st">${o.enabled ? 'zapnuto' : 'vypnuto'}</span></div>
    ${wt ? `<div class="wt">${esc(wt)}</div>` : ''}
    <dl><dt>Oktáva</dt><dd>${val(o.octave)}</dd>
    ${o.pitch != null ? `<dt>Půltóny</dt><dd>${f2(o.pitch)}</dd>` : ''}${o.fine != null ? `<dt>Fine</dt><dd>${f2(o.fine)}</dd>` : ''}
    <dt>Warp</dt><dd>${warp ? esc(warp) : dflt}</dd>
    <dt>Unison</dt><dd>${o.unison}</dd><dt>Detune</dt><dd>${val(o.detune)}${bar(o.detune)}</dd>
    <dt>Level</dt><dd>${val(o.level)}${bar(o.level)}</dd>${o.pan != null ? `<dt>Pan</dt><dd>${f2(o.pan)}</dd>` : ''}</dl></div>`;
}
function extraCard(title, about, x, rows) {
  return `<div class="osc small${x.enabled ? '' : ' off'}">
    <div class="oh"><b>${title}</b><span class="st">${x.enabled ? 'zapnuto' : 'vypnuto'}</span></div>
    <div class="about">${about}</div>
    <dl>${rows.filter(([, v]) => v !== undefined).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></div>`;
}
function renderBuild(b) {
  const oscs = [0, 1, 2].map((s) => oscCard(b.oscillators.find((o) => o.slot === s), s)).join('')
    + extraCard('Noise', 'šumový generátor, bez wavetable', b.noise, [['Level', `${val(b.noise.level)}${bar(b.noise.level)}`],
      ['Pan', b.noise.pan != null ? f2(b.noise.pan) : undefined], ['Pitch track', b.noise.pitch_track != null ? f2(b.noise.pitch_track) : undefined]])
    + extraCard('Sub', 'sinusový podtón pod hlavními oscilátory', b.sub, [['Level', `${val(b.sub.level)}${bar(b.sub.level)}`],
      ['Oktáva', val(b.sub.octave)], ['Coarse', b.sub.coarse != null ? f2(b.sub.coarse) : undefined], ['Pan', b.sub.pan != null ? f2(b.sub.pan) : undefined]]);
  const flt = b.filters.length
    ? b.filters.map((f) => `<div class="frow${f.on ? '' : ' off'}"><b>Filtr ${f.slot + 1}</b> ${esc(f.type || 'výchozí typ')} · cutoff ${val(f.freq)} · reso ${val(f.reso)} · drive ${val(f.drive)}${f.wet != null ? ' · wet ' + f2(f.wet) : ''}</div>`).join('')
    : '<div class="dim">bez filtru</div>';
  const fxItems = b.fx.map((e) => {
    const ps = Object.entries(e.params).filter(([k]) => KEYP.some((x) => k.endsWith(x))).slice(0, 5).map(([k, v]) => `${k.replace(/^kParam/, '')} ${f2(v)}`).join(' · ');
    const mode = e.mode ? ' <span class="m">' + esc(String(e.mode).replace(/^k/, '')) + '</span>' : '';
    return `<li${e.on ? '' : ' class="off"'}><b>${esc(FXN[e.module] || e.module)}</b>${mode}${e.on ? '' : ' <span class="dim">vypnuto</span>'}${ps ? `<div class="dim">${esc(ps)}</div>` : ''}</li>`;
  }).join('');
  const fx = b.fx.length ? `<ol class="fxl">${fxItems}</ol>` : '<div class="dim">bez FX</div>';
  const modItems = b.modulation.map((m) => `<li>${esc(m.source)} → ${esc(m.dest)} ${esc(m.param)} <span class="dim">${f2(m.amount)}</span></li>`).join('');
  const mod = b.modulation.length ? `<ul class="modl">${modItems}</ul>` : '<div class="dim">matice je prázdná</div>';
  const lfo = b.lfos.map((l) => `LFO ${l.index + 1}: ${esc(l.type || l.mode || 'výchozí')}${l.rate != null ? ' · rate ' + f2(l.rate) : ''}${l.points ? ' · ' + l.points + ' bodů' : ''}`).join(' · ');
  const mac = b.macros.map((m) => `M${m.index + 1} ${val(m.value)}`).join(' · ');
  const v = b.voice;
  const vo = [v.kParamMonoToggle === 1 ? 'mono' : 'poly', v.kParamLegato === 1 ? 'legato' : null, v.kParamPortamentoTime != null ? 'porta ' + f2(v.kParamPortamentoTime) : null].filter(Boolean).join(' · ');
  return `<div class="sec"><h3>Oscilátory</h3><div class="oscs">${oscs}</div></div>
    <div class="cols">
      <div class="sec"><h3>Filtry</h3>${flt}<h3 style="margin-top:16px">Hlas</h3><div>${vo}</div></div>
      <div class="sec"><h3>FX řetěz (v pořadí)</h3>${fx}</div>
    </div>
    <div class="sec"><h3>Modulace</h3>${mod}${lfo ? `<div class="dim" style="margin-top:6px">${lfo}</div>` : ''}${mac ? `<div class="dim">Makra: ${mac}</div>` : ''}</div>
    <div class="pnote">Serum 2 má tři wavetable oscilátory (A–C) a k nim Noise a Sub; v souboru se jmenují <code>NoiseOsc3</code> a <code>SubOsc4</code>. Hodnoty jsou přímo ze souboru (normalizované, jednotky neověřené proti Serum UI); „výchozí“ = v souboru chybí. Zdroje modulace mimo LFO, obálky a makra zatím nejsou pojmenované.</div>`;
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
      <div class="tags"><span class="tag">${esc(FN[p.function] || p.function)}</span>${archTag(p)}<span class="tag hyp" title="Funkce a archetyp jsou návrh z heuristiky (jméno + stopy v souboru)">hypotéza</span></div>
      <div class="cues">${cueList(p).map(esc).join(' <span class="dim">·</span> ')}</div>
      ${(p.why || []).length ? `<div class="why">Proč tenhle návrh: ${esc(p.why.join('; '))}</div>` : ''}
      <div class="meta">${esc(p.synth || '')}${(p.tags || []).length ? ' · tagy ve Seru: ' + esc(p.tags.join(', ')) : ''}</div></div>`;
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
  $('#filters').open = !isNarrow();
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
