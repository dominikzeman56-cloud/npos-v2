// Co dál?: guided "I'm stuck" decision helper (data: knowledge/guides/next-step.json via /data/next-step.json or /api/next-step).
'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lsGet = (k, d) => { try { const v = localStorage.getItem('vault.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('vault.' + k, JSON.stringify(v)); } catch { /* private mode */ } };
const CONF = { measured: 'naměřeno / ukázáno ve videu', estimated: 'odhad (heuristika)', hypothesis: 'hypotéza' };

let D = { phases: [], items: [] };
const S = { p: null, s: null, q: '' };

const byId = (id) => D.items.find((i) => i.id === id);
const phase = (id) => D.phases.find((p) => p.id === id);
// inline `code` in the JSON strings
const rich = (s) => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>');
const noteLink = (it) => '/#' + encodeURIComponent(it.vault.replace(/\.md$/, '') + '.md') + (it.anchor ? '::' + encodeURIComponent(it.anchor.replace(/`/g, '')) : '');

function readUrl() { const u = new URLSearchParams(location.search); S.p = u.get('p'); S.s = u.get('s'); S.q = u.get('q') || ''; }
function urlFor() {
  const u = new URLSearchParams();
  if (S.p) u.set('p', S.p); if (S.s) u.set('s', S.s); if (S.q) u.set('q', S.q);
  const x = u.toString(); return location.pathname + (x ? '?' + x : '');
}
function go(p, s, push = true) {
  S.p = p; S.s = s; S.q = ''; $('#q').value = '';
  if (push) history.pushState(null, '', urlFor()); else history.replaceState(null, '', urlFor());
  render(); scrollTo({ top: 0, behavior: 'instant' });
}

function crumbs() {
  const parts = [`<button type="button" data-go="">Kde jsi?</button>`];
  if (S.q) parts.push(`<span>hledání „${esc(S.q)}“</span>`);
  else {
    const it = S.s && byId(S.s);
    const ph = phase(it ? it.phase : S.p);
    if (ph) parts.push(`<span>›</span><button type="button" data-go="${esc(ph.id)}">${esc(ph.title)}</button>`);
    if (it) parts.push(`<span>›</span><span>${esc(it.situation)}</span>`);
  }
  $('#crumbs').innerHTML = parts.join(' ');
}

function sitButton(it, withPhase) {
  const ph = phase(it.phase);
  return `<button type="button" class="sit" data-s="${esc(it.id)}">${esc(it.situation)}${withPhase && ph ? `<small>${esc(ph.title)}</small>` : ''}</button>`;
}

function renderAnswer(it) {
  const follow = (it.then || []).map(byId).filter(Boolean);
  return `<article class="answer"><h2>${esc(it.situation)}</h2>
    <ol>${it.steps.map((x) => `<li>${rich(x)}</li>`).join('')}</ol>
    <div class="why"><span>Odkud:</span>${it.sources.map((x) => `<span class="pill">${esc(x)}</span>`).join('')}<span class="pill conf" title="Míra jistoty">${esc(CONF[it.confidence] || it.confidence)}</span></div>
    <a class="open" href="${noteLink(it)}">Otevřít v kánonu: ${esc(it.vault.split('/').pop())} →</a></article>
    ${follow.length ? `<div class="then"><div class="step-h">Pořád to nejde? Zkus potom</div><div class="sits">${follow.map((f) => sitButton(f, true)).join('')}</div></div>` : ''}`;
}

function render() {
  crumbs();
  const v = $('#view');
  if (S.q) {
    const hits = window.NposAdvisor ? NposAdvisor.search(D.items, S.q, S.p) : [];
    v.innerHTML = hits.length ? `<div class="step-h">${hits.length} nalezeno</div><div class="sits">${hits.map((i) => sitButton(i, true)).join('')}</div>` : '<div class="none">Nic nenalezeno. Zkus kratší slovo.</div>';
    return;
  }
  const it = S.s && byId(S.s);
  if (it) { v.innerHTML = renderAnswer(it); return; }
  const ph = S.p && phase(S.p);
  if (ph) {
    const items = D.items.filter((i) => i.phase === ph.id);
    v.innerHTML = `<div class="step-h">${esc(ph.title)}: co tě trápí?</div><div class="sits">${items.map((i) => sitButton(i, false)).join('')}</div>`;
    return;
  }
  v.innerHTML = `<div class="step-h">1 · Kde jsi?</div><div class="tiles">${D.phases.map((p) => {
    const n = D.items.filter((i) => i.phase === p.id).length;
    return `<button type="button" class="tile" data-p="${esc(p.id)}"><i>${n}</i><b>${esc(p.title)}</b><span>${esc(p.hint)}</span></button>`;
  }).join('')}</div>`;
}

function applyTheme() {
  const t = lsGet('skin', 'samurai');
  document.documentElement.dataset.theme = t;
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', ({ light: '#ffffff', samurai: '#0b0f14' })[t] || '#1e1e1e');
}
async function load() {
  for (const url of ['/data/next-step.json', '/api/next-step']) {
    try { const r = await fetch(url); if (r.ok && (r.headers.get('content-type') || '').includes('json')) return r.json(); } catch { /* next */ }
  }
  throw new Error('data nenalezena');
}

(async () => {
  applyTheme();
  const sk = $('#skin'); sk.value = lsGet('skin', 'samurai');
  sk.addEventListener('change', () => { lsSet('skin', sk.value); applyTheme(); });
  readUrl(); $('#q').value = S.q;
  try { D = await load(); } catch (e) { $('#intro').textContent = 'Chyba: ' + e.message; return; }
  $('#intro').textContent = D.note;
  $('#foot').innerHTML = `${D.items.length} situací v ${D.phases.length} fázích. Všechno jsou heuristiky se zdrojem a štítkem jistoty, ne zákony: zdroje a čísla jsou startovní bod (P9). `
    + 'Zdroj dat: <code>knowledge/guides/next-step.json</code>, odkazy míří do kánonu ve vaultu.';
  $('#q').addEventListener('input', (e) => { S.q = e.target.value.trim(); if (S.q) { S.p = null; S.s = null; } history.replaceState(null, '', urlFor()); render(); });
  $('#crumbs').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; go(b.dataset.go || null, null); });
  $('#view').addEventListener('click', (e) => {
    const t = e.target.closest('[data-p]'); if (t) return go(t.dataset.p, null);
    const s = e.target.closest('[data-s]'); if (s) { const it = byId(s.dataset.s); go(it.phase, it.id); }
  });
  addEventListener('popstate', () => { readUrl(); $('#q').value = S.q; render(); });
  render();
})();
