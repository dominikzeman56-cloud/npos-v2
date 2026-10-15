// NPOS/CTRL dashboard: personal scratchpad for the track you are working on. State lives only in this browser (localStorage);
// nothing is sent anywhere. The "Poradce" searches the Co dál? decision tree (knowledge/guides/next-step.json), it is not an AI.
'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lsGet = (k, d) => { try { const v = localStorage.getItem('vault.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('vault.' + k, JSON.stringify(v)); return true; } catch { return false; } };

const FIELDS = [
  ['title', 'Název'], ['bpm', 'Tempo (BPM)'], ['key', 'Tónina'], ['goal', 'Cíl'], ['reference', 'Reference'],
  ['problem', 'Hlavní problém', 'bad'], ['bass', 'Basa (archetyp)'], ['confidence', 'Jistota (%)'],
];
const EMPTY = { track: {}, stage: null, last: '', next: '', notes: [], tasks: [], sessions: [] };
let D = Object.assign({}, EMPTY, lsGet('dash', {}));
let NS = { phases: [], items: [] };
const save = () => { const ok = lsSet('dash', D); try { renderStatus(); } catch { /* before first render */ } $('#saved').textContent = ok ? 'uloženo jen v tomhle prohlížeči' : 'nelze uložit (soukromý režim?)'; };
const stamp = () => new Date().toLocaleString('cs-CZ', { day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit' });
const li = (h) => { const d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; };

function renderTrack() {
  $('#track').innerHTML = FIELDS.map(([k, l, c]) => `<div class="fld ${c || ''}"><label for="f-${k}">${esc(l)}</label><input id="f-${k}" data-k="${k}" value="${esc(D.track[k] || '')}" autocomplete="off"></div>`).join('');
  $('#track').oninput = (e) => { const k = e.target.dataset.k; if (k) { D.track[k] = e.target.value; save(); } };
}

function renderPipe() {
  const idx = NS.phases.findIndex((p) => p.id === D.stage);
  $('#pipe').innerHTML = NS.phases.map((p, i) => `<button type="button" class="st${i === idx ? ' cur' : i < idx ? ' done' : ''}" data-p="${esc(p.id)}"><small>${i === idx ? 'aktuální' : i < idx ? 'hotovo' : 'další'}</small><b>${esc(p.title)}</b></button>`).join('');
  const ph = NS.phases[idx];
  const items = ph ? NS.items.filter((i) => i.phase === ph.id) : [];
  $('#phaseHelp').innerHTML = ph
    ? `Co dál? pro fázi <b>${esc(ph.title)}</b>: ${items.map((i) => `<a href="/dal.html?p=${esc(i.phase)}&s=${esc(i.id)}">${esc(i.situation)}</a>`).join(' · ')}`
    : 'Vyber fázi, ve které teď jsi: tady se ti zobrazí situace z „Co dál?“.';
}

function renderNotes() {
  const L = { breakthrough: 'průlom', issue: 'issue', idea: 'idea' };
  $('#notes').innerHTML = D.notes.length ? D.notes.map((n, i) => `<div class="it"><span class="tag ${esc(n.type)}">${esc(L[n.type] || n.type)}</span><span class="tx">${esc(n.text)}</span><span class="when">${esc(n.when)}</span><button class="x" data-del="${i}" aria-label="Smazat">×</button></div>`).join('') : '<div class="empty-l">zatím nic</div>';
}
function renderTasks() {
  const done = D.tasks.filter((t) => t.done).length;
  $('#pct').innerHTML = D.tasks.length ? `${done}/${D.tasks.length} <span class="bar"><i style="width:${Math.round(100 * done / D.tasks.length)}%"></i></span>` : '';
  $('#tasks').innerHTML = D.tasks.length ? D.tasks.map((t, i) => `<div class="it${t.done ? ' done' : ''}"><input type="checkbox" data-chk="${i}" ${t.done ? 'checked' : ''} aria-label="Hotovo"><span class="tx">${esc(t.text)}</span><button class="x" data-del="${i}" aria-label="Smazat">×</button></div>`).join('') : '<div class="empty-l">zatím nic</div>';
}
function renderSess() {
  $('#sess').innerHTML = D.sessions.length ? D.sessions.map((s, i) => `<div class="it"><span class="tx"><b>${esc(s.title)}</b>${s.sum ? '<br><span class="muted">' + esc(s.sum) + '</span>' : ''}</span><span class="when">${esc(s.when)}</span><button class="x" data-del="${i}" aria-label="Smazat">×</button></div>`).join('') : '<div class="empty-l">zatím nic</div>';
}

// Advisor: simple keyword match over the Co dál? items (situation, steps, sources), best hits first.
function ask(q) {
  const words = q.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => w.length > 2);
  if (!words.length) { $('#ans').innerHTML = ''; return; }
  const score = (it) => { const hay = (it.situation + ' ' + it.steps.join(' ') + ' ' + it.sources.join(' ')).toLowerCase(); const base = words.reduce((a, w) => a + (it.situation.toLowerCase().includes(w) ? 3 : 0) + (hay.includes(w) ? 1 : 0), 0); return base > 0 && it.phase === D.stage ? base + 2 : base; }; // current phase wins ties
  const hits = NS.items.map((it) => [score(it), it]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, 3).map(([, it]) => it);
  $('#ans').innerHTML = hits.length ? hits.map((it) => `<div class="hit"><b>${esc(it.situation)}</b><ol>${it.steps.slice(0, 3).map((s) => `<li>${esc(s).replace(/`([^`]+)`/g, '<code>$1</code>')}</li>`).join('')}</ol><a href="/dal.html?p=${esc(it.phase)}&s=${esc(it.id)}">Celý postup →</a> <span class="muted">· ${esc(it.confidence === 'estimated' ? 'odhad' : it.confidence)}</span></div>`).join('')
    : '<div class="hit"><b>Nic nenalezeno</b><span class="muted">Zkus kratší slovo, nebo projdi fáze v <a href="/dal.html">Co dál?</a>.</span></div>';
}

function wire() {
  $('#pipe').onclick = (e) => { const b = e.target.closest('[data-p]'); if (!b) return; D.stage = b.dataset.p; save(); renderPipe(); };
  for (const k of ['last', 'next']) { const el = $('#' + k); el.value = D[k] || ''; el.oninput = () => { D[k] = el.value; save(); }; }
  const addNote = () => { const t = $('#ntx').value.trim(); if (!t) return; D.notes.unshift({ type: $('#nt').value, text: t, when: stamp() }); $('#ntx').value = ''; save(); renderNotes(); };
  $('#nadd').onclick = addNote; $('#ntx').onkeydown = (e) => { if (e.key === 'Enter') addNote(); };
  $('#notes').onclick = (e) => { const b = e.target.closest('[data-del]'); if (b) { D.notes.splice(+b.dataset.del, 1); save(); renderNotes(); } };
  const addTask = () => { const t = $('#ttx').value.trim(); if (!t) return; D.tasks.push({ text: t, done: false }); $('#ttx').value = ''; save(); renderTasks(); };
  $('#tadd').onclick = addTask; $('#ttx').onkeydown = (e) => { if (e.key === 'Enter') addTask(); };
  $('#tasks').onclick = (e) => {
    const b = e.target.closest('[data-del]'); if (b) { D.tasks.splice(+b.dataset.del, 1); save(); renderTasks(); return; }
    const c = e.target.closest('[data-chk]'); if (c) { D.tasks[+c.dataset.chk].done = c.checked; save(); renderTasks(); }
  };
  $('#sadd').onclick = () => { const title = prompt('Název session (např. „Sound design: body layer“)'); if (!title) return; const sum = prompt('Krátké shrnutí (nepovinné)') || ''; D.sessions.unshift({ title, sum, when: stamp() }); save(); renderSess(); };
  $('#sess').onclick = (e) => { const b = e.target.closest('[data-del]'); if (b) { D.sessions.splice(+b.dataset.del, 1); save(); renderSess(); } };
  const go = () => ask($('#q').value);
  $('#go').onclick = go; $('#q').onkeydown = (e) => { if (e.key === 'Enter') go(); };
  $('#exp').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(D, null, 1)], { type: 'application/json' })); a.download = 'npos-ctrl-zaloha.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
  $('#imp').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { const j = JSON.parse(await f.text()); if (typeof j !== 'object' || !j) throw 0; D = Object.assign({}, EMPTY, j); save(); renderAll(); } catch { alert('Soubor se nepodařilo načíst (není to záloha z tohohle dashboardu).'); }
    e.target.value = '';
  };
  const sk = $('#skin'); sk.value = lsGet('skin', 'samurai');
  sk.onchange = () => { lsSet('skin', sk.value); document.documentElement.dataset.theme = sk.value; };
}
function renderStatus() {
  const T = D.track, ph = NS.phases.find((p) => p.id === D.stage), done = D.tasks.filter((x) => x.done).length;
  const bits = [T.title && 'TRACK: ' + T.title, T.bpm && T.bpm + ' BPM', T.key && 'TÓNINA: ' + T.key, ph && 'FÁZE: ' + ph.title, D.tasks.length && `ÚKOLY: ${done}/${D.tasks.length}`].filter(Boolean);
  $('#status').textContent = bits.length ? bits.join('  ·  ') : 'vyplň aktuální track a vyber fázi';
}
function renderAll() { renderTrack(); renderPipe(); renderNotes(); renderTasks(); renderSess(); renderStatus(); for (const k of ['last', 'next']) $('#' + k).value = D[k] || ''; }

addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === 'k') { e.preventDefault(); $('#q').focus(); }
  else if (k === 'j') { e.preventDefault(); $('#sadd').click(); }
});
(async () => {
  wire();
  try { for (const u of ['/data/next-step.json', '/api/next-step']) { const r = await fetch(u); if (r.ok && (r.headers.get('content-type') || '').includes('json')) { NS = await r.json(); break; } } } catch { /* offline: dashboard still works */ }
  $('#quick').innerHTML = ['basa slabá', 'kick maskuje', 'drop plochý', 'zní generic', 'Live padá'].map((t) => `<button class="btn" type="button" data-q="${esc(t)}">${esc(t)}</button>`).join('');
  $('#quick').onclick = (e) => { const b = e.target.closest('[data-q]'); if (b) { $('#q').value = b.dataset.q; ask(b.dataset.q); } };
  renderAll();
})();
