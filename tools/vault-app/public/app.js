'use strict';
// Obsidian-like read-only vault viewer (client). No build step: markdown-it + d3 come from /vendor.

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const enc = encodeURIComponent;
const lsGet = (k, d) => { try { const v = localStorage.getItem('vault.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('vault.' + k, JSON.stringify(v)); } catch { /* ignore */ } };
// Static mode (Vercel export): everything comes from one /data/vault.json snapshot instead of the live API.
let DB = null, searchCore = null;
const assetUrl = (p) => (DB ? '/files/' + p.split('/').map(encodeURIComponent).join('/') : '/asset?path=' + encodeURIComponent(p));
function staticApi(p) {
  const u = new URL(p, location.origin), q = u.searchParams;
  switch (u.pathname) {
    case '/api/index': return DB.index;
    case '/api/note': { const n = DB.notes[q.get('path')]; if (!n) throw new Error('404'); return n; }
    case '/api/tags': return DB.tags;
    case '/api/graph': return DB.graph;
    case '/api/search': return searchCore.search(Object.values(DB.notes), q.get('q') || '');
    default: throw new Error('unknown ' + u.pathname);
  }
}
const api = async (p) => {
  if (DB) return staticApi(p);
  const r = await fetch(p); if (!r.ok) throw new Error(p + ' → ' + r.status); return r.json();
};
const dirOf = (p) => (p.includes('/') ? p.slice(0, p.lastIndexOf('/')) : '');
const nameOf = (p) => p.split('/').pop().replace(/\.md$/i, '');
const IMG = /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i;

const ICONS = {
  files: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  graph: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>',
  tags: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  switcher: '<path d="m13 2-9 12h7l-1 8 9-12h-7Z"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24">${ICONS[n]}</svg>`;
const CALLOUT_ICON = { note: '✎', info: 'ⓘ', todo: '☑', abstract: '☰', summary: '☰', tldr: '☰', tip: '✦', hint: '✦', success: '✓', check: '✓', done: '✓', question: '?', help: '?', faq: '?', warning: '⚠', caution: '⚠', attention: '⚠', failure: '✕', fail: '✕', missing: '✕', danger: '⚡', error: '⚡', bug: '✱', example: '≡', quote: '❝', cite: '❝' };

const S = {
  notes: [], noteSet: new Set(), vault: '',
  tabs: lsGet('tabs', []), active: lsGet('active', null),
  leftMode: lsGet('leftMode', 'files'), rightMode: lsGet('rightMode', 'backlinks'),
  expanded: new Set(lsGet('expanded', [])), theme: lsGet('theme', 'dark'),
  noLeft: lsGet('noLeft', false), noRight: lsGet('noRight', false),
  graphLocal: false, graphSim: null, current: null, scroll: {}, query: '', pendingHeading: null,
};
const CTX = { note: null };

/* ---------- markdown ---------- */
const md = window.markdownit({ html: false, linkify: true, breaks: true });

md.inline.ruler.before('link', 'wikilink', (state, silent) => {
  const src = state.src, pos = state.pos;
  let start = pos, embed = false;
  if (src.charCodeAt(pos) === 0x21 && src.startsWith('[[', pos + 1)) { embed = true; start = pos + 1; }
  else if (!src.startsWith('[[', pos)) return false;
  const end = src.indexOf(']]', start + 2);
  if (end < 0) return false;
  const inner = src.slice(start + 2, end);
  if (inner.includes('\n') || !inner.trim()) return false;
  if (!silent) state.push('wikilink', '', 0).meta = { embed, inner };
  state.pos = end + 2;
  return true;
});
md.renderer.rules.wikilink = (tokens, i) => renderWiki(tokens[i].meta);

md.inline.ruler.before('emphasis', 'obstag', (state, silent) => {
  const src = state.src, pos = state.pos;
  if (src.charCodeAt(pos) !== 0x23) return false;
  if (pos > 0 && !/\s/.test(src[pos - 1])) return false;
  const m = /^#([\p{L}\p{N}_\-/]+)/u.exec(src.slice(pos));
  if (!m || /^\d+$/.test(m[1])) return false;
  if (!silent) state.push('obstag', '', 0).meta = m[1];
  state.pos += m[0].length;
  return true;
});
md.renderer.rules.obstag = (tokens, i) => `<a class="tag" data-tag="${esc(tokens[i].meta)}">#${esc(tokens[i].meta)}</a>`;

function renderWiki({ embed, inner }) {
  const bar = inner.indexOf('|');
  const target = bar < 0 ? inner : inner.slice(0, bar);
  const alias = bar < 0 ? '' : inner.slice(bar + 1);
  const [fileRaw, ...hs] = target.split('#');
  const heading = hs.join('#').trim();
  const key = fileRaw.split('^')[0].trim();
  if (!key) return `<a class="internal-link" data-href="" data-heading="${esc(heading)}">${esc(alias || '#' + heading)}</a>`;
  const resolved = CTX.note?.links?.[key] || null;
  const label = alias || key + (heading ? ' > ' + heading : '');
  if (embed) {
    if (!resolved) return `<span class="is-unresolved">${esc(label)}</span>`;
    if (IMG.test(resolved)) {
      const w = /^\d+$/.test(alias) ? ` width="${alias}"` : '';
      return `<img src="${esc(assetUrl(resolved))}" alt="${esc(key)}"${w}>`;
    }
    if (/\.(mp3|wav|ogg)$/i.test(resolved)) return `<audio controls src="${esc(assetUrl(resolved))}"></audio>`;
    if (/\.(mp4|webm)$/i.test(resolved)) return `<video controls src="${esc(assetUrl(resolved))}" style="max-width:100%"></video>`;
    if (/\.md$/i.test(resolved)) return `<div class="embed-block" data-embed="${esc(resolved)}" data-heading="${esc(heading)}"></div>`;
    return `<a href="${esc(assetUrl(resolved))}" target="_blank" rel="noopener">${esc(label)}</a>`;
  }
  const dead = resolved ? '' : ' is-unresolved';
  return `<a class="internal-link${dead}" data-href="${esc(resolved || '')}" data-heading="${esc(heading)}">${esc(label)}</a>`;
}

const defLink = md.renderer.rules.link_open || ((t, i, o, e, s) => s.renderToken(t, i, o));
md.renderer.rules.link_open = (tokens, i, opts, env, self) => {
  const href = tokens[i].attrGet('href') || '';
  if (/^https?:/i.test(href)) { tokens[i].attrSet('target', '_blank'); tokens[i].attrSet('rel', 'noopener'); }
  return defLink(tokens, i, opts, env, self);
};

function renderMarkdown(note, depth = 0) {
  CTX.note = note;
  const box = document.createElement('div');
  box.className = 'markdown-rendered';
  box.innerHTML = md.render(note.body);
  postProcess(box, note, depth);
  return box;
}

function postProcess(root, note, depth) {
  root.querySelectorAll('blockquote').forEach((bq) => {
    const p = bq.firstElementChild;
    if (!p || p.tagName !== 'P') return;
    const html = p.innerHTML;
    const mm = html.match(/^\[!([\w-]+)\]([+-])?[ \t]*/);
    if (!mm) return;
    const rest = html.slice(mm[0].length);
    const br = rest.search(/<br>|\n/);
    const title = br < 0 ? rest : rest.slice(0, br);
    const after = br < 0 ? '' : rest.slice(br).replace(/^(<br>\s*|\n)/, '');
    const type = mm[1].toLowerCase();
    const div = document.createElement('div');
    div.className = 'callout' + (mm[2] === '-' ? ' is-collapsed' : '');
    div.dataset.callout = type;
    if (mm[2]) div.dataset.fold = '1';
    div.innerHTML = `<div class="callout-title"><span>${CALLOUT_ICON[type] || '✎'}</span><span>${title || esc(type[0].toUpperCase() + type.slice(1))}</span></div><div class="callout-content"></div>`;
    const content = div.querySelector('.callout-content');
    if (after.trim()) { p.innerHTML = after; content.append(p); } else p.remove();
    while (bq.firstChild) content.append(bq.firstChild);
    bq.replaceWith(div);
  });
  root.querySelectorAll('.callout[data-fold] .callout-title').forEach((t) =>
    t.addEventListener('click', () => t.parentElement.classList.toggle('is-collapsed')));

  root.querySelectorAll('li').forEach((li) => {
    const m = li.innerHTML.match(/^(<p>)?\[([ xX])\]\s/);
    if (!m) return;
    li.innerHTML = li.innerHTML.replace(/^(<p>)?\[([ xX])\]\s/, `$1<input type="checkbox" disabled ${m[2] !== ' ' ? 'checked' : ''}>`);
    li.classList.add('task-list-item');
    if (m[2] !== ' ') li.classList.add('done');
  });

  const base = dirOf(note.path);
  root.querySelectorAll('a[href]').forEach((a) => {
    const h = a.getAttribute('href');
    if (/^([a-z]+:|#|\/)/i.test(h)) return;
    let dec = h.split('#')[0]; try { dec = decodeURIComponent(dec); } catch { /* keep */ }
    const rel = normPosix((base ? base + '/' : '') + dec);
    if (S.noteSet.has(rel)) { a.classList.add('internal-link'); a.dataset.href = rel; a.removeAttribute('href'); }
  });
  root.querySelectorAll('img').forEach((img) => {
    const s = img.getAttribute('src') || '';
    if (/^([a-z]+:|\/)/i.test(s)) return;
    let dec = s; try { dec = decodeURIComponent(s); } catch { /* keep */ }
    img.src = assetUrl(normPosix((base ? base + '/' : '') + dec));
  });
  root.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach((h, i) => { h.id = 'h-' + i; });

  if (depth < 2) {
    root.querySelectorAll('.embed-block[data-embed]').forEach(async (blk) => {
      try {
        const n = await api('/api/note?path=' + enc(blk.dataset.embed));
        let body = n.body;
        const hd = blk.dataset.heading;
        if (hd) body = sliceSection(body, hd);
        const saved = CTX.note;
        blk.innerHTML = `<div class="embed-title">${esc(n.name)}</div>`;
        blk.append(renderMarkdown({ ...n, body }, depth + 1));
        CTX.note = saved;
      } catch { blk.textContent = '(nelze načíst vložený soubor)'; }
    });
  }
}

function normPosix(p) {
  const out = [];
  for (const part of p.split('/')) { if (part === '..') out.pop(); else if (part && part !== '.') out.push(part); }
  return out.join('/');
}

function sliceSection(body, heading) {
  const lines = body.split('\n');
  const want = heading.trim().toLowerCase();
  let start = -1, lvl = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,6})\s+(.*?)\s*#*$/);
    if (!m) continue;
    if (start < 0 && m[2].trim().toLowerCase() === want) { start = i; lvl = m[1].length; }
    else if (start >= 0 && m[1].length <= lvl) return lines.slice(start, i).join('\n');
  }
  return start >= 0 ? lines.slice(start).join('\n') : body;
}

/* ---------- tabs / navigation ---------- */
const saveTabs = () => { lsSet('tabs', S.tabs); lsSet('active', S.active); };
const tabById = (id) => S.tabs.find((t) => t.id === id);
const tabTitle = (t) => (t.kind === 'graph' ? 'Graf' : nameOf(t.path));

function openNote(path, { newTab = false, heading = null } = {}) {
  if (!path) return;
  S.pendingHeading = heading;
  const ex = S.tabs.find((t) => t.kind === 'note' && t.path === path);
  if (ex) S.active = ex.id;
  else {
    const cur = tabById(S.active);
    if (cur && cur.kind === 'note' && !newTab) { cur.path = path; }
    else { const id = 't' + Date.now() + Math.random().toString(36).slice(2, 5); S.tabs.push({ id, kind: 'note', path }); S.active = id; }
  }
  const parts = path.split('/'); parts.pop();
  parts.forEach((_, i) => S.expanded.add(parts.slice(0, i + 1).join('/')));
  lsSet('expanded', [...S.expanded]);
  saveTabs(); renderAll();
}
function openGraph() {
  let t = S.tabs.find((x) => x.kind === 'graph');
  if (!t) { t = { id: 'graph', kind: 'graph' }; S.tabs.push(t); }
  S.active = t.id; saveTabs(); renderAll();
}
function closeTab(id) {
  const i = S.tabs.findIndex((t) => t.id === id);
  if (i < 0) return;
  S.tabs.splice(i, 1);
  if (S.active === id) S.active = S.tabs[Math.min(i, S.tabs.length - 1)]?.id || null;
  saveTabs(); renderAll();
}

/* ---------- layout pieces ---------- */
function renderRibbon() {
  const items = [
    ['files', 'files', 'Soubory', () => setLeft('files')],
    ['search', 'search', 'Hledat (Ctrl+Shift+F)', () => setLeft('search')],
    ['tags', 'tags', 'Tagy', () => setLeft('tags')],
    ['graph', 'graph', 'Graf (Ctrl+G)', openGraph],
    ['switcher', 'switcher', 'Rychlé otevření (Ctrl+O)', quickSwitcher],
  ];
  const r = $('#ribbon'); r.innerHTML = '';
  for (const [id, ic, title, fn] of items) {
    const b = document.createElement('button');
    b.className = 'rb' + (S.leftMode === id && !S.noLeft && ['files', 'search', 'tags'].includes(id) ? ' on' : '');
    b.title = title; b.innerHTML = icon(ic); b.onclick = fn; r.append(b);
  }
  r.insertAdjacentHTML('beforeend', '<div class="sp"></div>');
  const t = document.createElement('button');
  t.className = 'rb'; t.title = 'Světlý / tmavý režim'; t.innerHTML = icon('moon');
  t.onclick = () => { S.theme = S.theme === 'dark' ? 'light' : 'dark'; lsSet('theme', S.theme); applyTheme(); renderAll(); };
  r.append(t);
}
function setLeft(mode) {
  if (S.leftMode === mode && !S.noLeft) S.noLeft = true; else { S.leftMode = mode; S.noLeft = false; }
  lsSet('leftMode', S.leftMode); lsSet('noLeft', S.noLeft);
  applyLayout(); renderRibbon(); renderLeft();
  if (mode === 'search') setTimeout(() => $('#left .searchbox input')?.focus(), 0);
}
function applyLayout() {
  $('#app').classList.toggle('no-left', S.noLeft);
  $('#app').classList.toggle('no-right', S.noRight);
}
function applyTheme() { document.documentElement.dataset.theme = S.theme; }

function renderTabs() {
  const bar = $('#tabbar'); bar.innerHTML = '<div id="tabs"></div>';
  const wrap = $('#tabs', bar);
  for (const t of S.tabs) {
    const d = document.createElement('div');
    d.className = 'tab' + (t.id === S.active ? ' on' : '');
    d.innerHTML = `<span class="nm">${esc(tabTitle(t))}</span><span class="x">×</span>`;
    d.onclick = (e) => { if (e.target.classList.contains('x')) return closeTab(t.id); S.active = t.id; saveTabs(); renderAll(); };
    d.onauxclick = (e) => { if (e.button === 1) closeTab(t.id); };
    wrap.append(d);
  }
  const tb = document.createElement('button');
  tb.className = 'tb'; tb.title = 'Pravý panel'; tb.innerHTML = icon('panel');
  tb.onclick = () => { S.noRight = !S.noRight; lsSet('noRight', S.noRight); applyLayout(); };
  bar.append(tb);
}

/* left sidebar */
function renderLeft() {
  const head = $('#left .side-head'), body = $('#left .side-body');
  head.innerHTML = '';
  for (const [id, label] of [['files', 'Soubory'], ['search', 'Hledat'], ['tags', 'Tagy']]) {
    const b = document.createElement('button');
    b.textContent = label; b.className = S.leftMode === id ? 'on' : '';
    b.onclick = () => { S.leftMode = id; lsSet('leftMode', id); renderLeft(); renderRibbon(); };
    head.append(b);
  }
  body.innerHTML = '';
  if (S.leftMode === 'files') renderTree(body);
  else if (S.leftMode === 'search') renderSearch(body);
  else renderTags(body);
}

function buildTree(paths) {
  const root = { children: new Map(), files: [] };
  for (const p of paths) {
    const parts = p.split('/'); let n = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i];
      if (!n.children.has(k)) n.children.set(k, { name: k, path: parts.slice(0, i + 1).join('/'), children: new Map(), files: [] });
      n = n.children.get(k);
    }
    n.files.push(p);
  }
  return root;
}
const cmp = (a, b) => a.localeCompare(b, 'cs', { numeric: true, sensitivity: 'base' });

function renderTree(body) {
  const root = buildTree(S.notes.map((n) => n.path));
  const activePath = tabById(S.active)?.path;
  const draw = (node, depth, into) => {
    for (const f of [...node.children.values()].sort((a, b) => cmp(a.name, b.name))) {
      const open = S.expanded.has(f.path);
      const row = document.createElement('div');
      row.className = 'tree-row folder'; row.style.paddingLeft = 6 + depth * 14 + 'px';
      row.innerHTML = `<span class="chev${open ? ' open' : ''}">▶</span><span class="nm">${esc(f.name)}</span>`;
      row.onclick = () => { open ? S.expanded.delete(f.path) : S.expanded.add(f.path); lsSet('expanded', [...S.expanded]); renderLeft(); };
      into.append(row);
      if (open) draw(f, depth + 1, into);
    }
    for (const p of node.files.sort((a, b) => cmp(nameOf(a), nameOf(b)))) {
      const row = document.createElement('div');
      row.className = 'tree-row' + (p === activePath ? ' active' : ''); row.style.paddingLeft = 6 + depth * 14 + 14 + 'px';
      row.innerHTML = `<span class="nm">${esc(nameOf(p))}</span>`; row.title = p;
      row.onclick = (e) => openNote(p, { newTab: e.ctrlKey || e.metaKey });
      row.onauxclick = (e) => { if (e.button === 1) openNote(p, { newTab: true }); };
      into.append(row);
    }
  };
  draw(root, 0, body);
  body.querySelector('.tree-row.active')?.scrollIntoView({ block: 'nearest' });
}

let searchTimer = null;
function renderSearch(body) {
  body.innerHTML = '<div class="searchbox"><input placeholder="Hledat… (tag:nazev)" spellcheck="false"></div><div id="sres"></div>';
  const inp = $('input', body);
  inp.value = S.query;
  const run = async () => {
    S.query = inp.value.trim();
    const box = $('#sres', body);
    if (!S.query) { box.innerHTML = '<div class="hint">Zadej hledaný text. Filtr podle tagu: <kbd>tag:neurofunk</kbd></div>'; return; }
    const r = await api('/api/search?q=' + enc(S.query));
    box.innerHTML = `<div class="hint">${r.total} výsledků</div>`;
    const re = r.terms.length ? new RegExp('(' + r.terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'ig') : null;
    for (const x of r.results) {
      const d = document.createElement('div'); d.className = 'res';
      const sn = re ? esc(x.snippet).replace(re, '<mark>$1</mark>') : esc(x.snippet);
      d.innerHTML = `<div class="t">${esc(nameOf(x.path))}</div><div class="pth">${esc(dirOf(x.path))}</div><div class="sn">${sn}</div>`;
      d.onclick = (e) => openNote(x.path, { newTab: e.ctrlKey || e.metaKey });
      box.append(d);
    }
  };
  inp.oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(run, 220); };
  run();
}

async function renderTags(body) {
  const tags = await api('/api/tags');
  body.innerHTML = tags.length ? '' : '<div class="hint">Žádné tagy.</div>';
  for (const t of tags) {
    const d = document.createElement('div'); d.className = 'tagrow';
    d.innerHTML = `<span>#${esc(t.tag)}</span><span class="c">${t.count}</span>`;
    d.onclick = () => searchTag(t.tag);
    body.append(d);
  }
}
function searchTag(tag) {
  S.query = 'tag:' + tag; S.leftMode = 'search'; S.noLeft = false;
  lsSet('leftMode', 'search'); lsSet('noLeft', false);
  applyLayout(); renderLeft(); renderRibbon();
}

/* right sidebar */
function renderRight() {
  const head = $('#right .side-head'), body = $('#right .side-body');
  head.innerHTML = '';
  for (const [id, label] of [['backlinks', 'Zpětné odkazy'], ['outgoing', 'Odkazy'], ['outline', 'Osnova']]) {
    const b = document.createElement('button');
    b.textContent = label; b.className = S.rightMode === id ? 'on' : '';
    b.onclick = () => { S.rightMode = id; lsSet('rightMode', id); renderRight(); };
    head.append(b);
  }
  body.innerHTML = '';
  const n = S.current;
  if (!n) { body.innerHTML = '<div class="hint">Žádná poznámka.</div>'; return; }
  const item = (p, dead) => {
    const d = document.createElement('div');
    d.className = 'link-item' + (dead ? ' dead' : ''); d.textContent = dead ? p : nameOf(p); d.title = p;
    if (!dead) d.onclick = (e) => openNote(p, { newTab: e.ctrlKey || e.metaKey });
    return d;
  };
  if (S.rightMode === 'backlinks') {
    if (!n.backlinks.length) body.innerHTML = '<div class="hint">Nikdo na tuhle poznámku neodkazuje.</div>';
    n.backlinks.slice().sort(cmp).forEach((p) => body.append(item(p)));
  } else if (S.rightMode === 'outgoing') {
    const seen = new Set(); let any = false;
    for (const o of n.outgoing) {
      const k = o.resolved || o.target;
      if (seen.has(k)) continue; seen.add(k); any = true;
      body.append(item(o.resolved || o.target, !o.resolved));
    }
    if (!any) body.innerHTML = '<div class="hint">Žádné odkazy.</div>';
  } else {
    const hs = [...$('#pane .markdown-rendered')?.querySelectorAll('h1,h2,h3,h4,h5,h6') || []];
    if (!hs.length) body.innerHTML = '<div class="hint">Žádné nadpisy.</div>';
    for (const h of hs) {
      const d = document.createElement('div'); d.className = 'outline-item';
      d.style.paddingLeft = 8 + (Number(h.tagName[1]) - 1) * 12 + 'px'; d.textContent = h.textContent;
      d.onclick = () => h.scrollIntoView({ behavior: 'smooth', block: 'start' });
      body.append(d);
    }
  }
}

/* ---------- main pane ---------- */
async function renderPane() {
  const pane = $('#pane');
  if (S.graphSim) { S.graphSim.stop(); S.graphSim = null; }
  const prev = S.current?.path;
  if (prev) S.scroll[prev] = pane.scrollTop;
  const t = tabById(S.active);
  S.current = null;
  $('#statusbar').textContent = '';
  if (!t) {
    pane.innerHTML = '<div class="empty"><div>Žádná otevřená poznámka<br><kbd>Ctrl</kbd> + <kbd>O</kbd> rychlé otevření · <kbd>Ctrl</kbd> + <kbd>G</kbd> graf</div></div>';
    return renderRight();
  }
  if (t.kind === 'graph') { renderGraph(pane); return renderRight(); }
  pane.innerHTML = '<div class="note"><div class="hint">Načítám…</div></div>';
  let n;
  try { n = await api('/api/note?path=' + enc(t.path)); }
  catch { pane.innerHTML = `<div class="empty"><div>Poznámka <b>${esc(t.path)}</b> neexistuje.<br>Možná byla přesunutá nebo smazaná.</div></div>`; return renderRight(); }
  if (tabById(S.active) !== t) return;
  S.current = n;
  const wrap = document.createElement('div'); wrap.className = 'note';
  wrap.innerHTML = `<h1 class="inline-title">${esc(n.name)}</h1>`;
  wrap.append(renderProps(n));
  wrap.append(renderMarkdown(n));
  pane.innerHTML = ''; pane.append(wrap);
  wireLinks(wrap);
  const words = (n.body.match(/\S+/g) || []).length;
  $('#statusbar').textContent = `${n.backlinks.length} zpětných odkazů · ${words} slov · ${n.body.length} znaků`;
  if (S.pendingHeading) { scrollToHeading(S.pendingHeading); S.pendingHeading = null; }
  else pane.scrollTop = S.scroll[n.path] || 0;
  renderRight();
}

function renderProps(n) {
  const keys = Object.keys(n.fm).filter((k) => !(Array.isArray(n.fm[k]) && !n.fm[k].length));
  const box = document.createElement('div');
  if (!keys.length) return box;
  box.className = 'props';
  box.innerHTML = '<div class="ph">Vlastnosti</div>';
  for (const k of keys) {
    const v = n.fm[k];
    const row = document.createElement('div'); row.className = 'prop';
    const isTags = /^tags?$/i.test(k) || Array.isArray(v);
    const val = isTags ? [].concat(v).map((x) => `<span class="chip">${esc(x)}</span>`).join('') : esc(v);
    row.innerHTML = `<div class="k">${esc(k)}</div><div class="v">${val}</div>`;
    box.append(row);
  }
  return box;
}

function scrollToHeading(h) {
  const want = h.trim().toLowerCase();
  for (const el of $('#pane').querySelectorAll('h1,h2,h3,h4,h5,h6'))
    if (el.textContent.trim().toLowerCase() === want) { el.scrollIntoView({ block: 'start' }); return; }
}

function wireLinks(root) {
  root.addEventListener('click', (e) => {
    const tag = e.target.closest('a.tag');
    if (tag) { e.preventDefault(); return searchTag(tag.dataset.tag); }
    const a = e.target.closest('a.internal-link');
    if (!a) return;
    e.preventDefault();
    const href = a.dataset.href;
    if (!href) { if (a.dataset.heading) scrollToHeading(a.dataset.heading); return; }
    openNote(href, { newTab: e.ctrlKey || e.metaKey, heading: a.dataset.heading || null });
  });
}

/* ---------- graph ---------- */
async function renderGraph(pane) {
  pane.innerHTML = `<div id="graph-wrap"><canvas></canvas>
    <div class="graph-ctl"><label><input type="checkbox" id="g-local"> Jen okolí aktivní poznámky</label>
    <label><input type="checkbox" id="g-labels" checked> Popisky</label></div></div>`;
  const wrap = $('#graph-wrap'), canvas = $('canvas', wrap), ctx = canvas.getContext('2d');
  const g = await api('/api/graph');
  const lastNote = [...S.tabs].reverse().find((t) => t.kind === 'note')?.path;
  $('#g-local').checked = S.graphLocal;
  let nodes, links, sim, T = d3.zoomIdentity, hover = null;
  const hue = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };

  const build = () => {
    let ns = g.nodes, ls = g.links;
    if (S.graphLocal && lastNote) {
      const keep = new Set([lastNote]);
      ls.forEach(([a, b]) => { if (a === lastNote) keep.add(b); if (b === lastNote) keep.add(a); });
      ns = ns.filter((n) => keep.has(n.id)); ls = ls.filter(([a, b]) => keep.has(a) && keep.has(b));
    }
    nodes = ns.map((n) => ({ ...n }));
    links = ls.map(([source, target]) => ({ source, target }));
    if (sim) sim.stop();
    sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(38).strength(0.45))
      .force('charge', d3.forceManyBody().strength(-55))
      .force('x', d3.forceX().strength(0.04)).force('y', d3.forceY().strength(0.04))
      .force('collide', d3.forceCollide(6))
      .on('tick', draw);
    S.graphSim = sim;
  };
  const resize = () => {
    const r = wrap.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    canvas.width = r.width * dpr; canvas.height = r.height * dpr; draw();
  };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const radius = (d) => 3 + Math.min(Math.sqrt(d.deg) * 1.4, 9);

  function draw() {
    const dpr = window.devicePixelRatio || 1, w = canvas.width / dpr, h = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(T.x + w / 2, T.y + h / 2); ctx.scale(T.k, T.k);
    ctx.strokeStyle = css('--graph-line'); ctx.lineWidth = 1 / T.k;
    ctx.beginPath();
    for (const l of links) { ctx.moveTo(l.source.x, l.source.y); ctx.lineTo(l.target.x, l.target.y); }
    ctx.stroke();
    const showLabels = $('#g-labels')?.checked;
    const acc = css('--accent'), txt = css('--text'), dark = S.theme === 'dark';
    ctx.font = `${11 / Math.sqrt(T.k)}px sans-serif`; ctx.textAlign = 'center';
    for (const d of nodes) {
      const isA = d.id === lastNote, isH = d === hover;
      ctx.beginPath(); ctx.arc(d.x, d.y, radius(d) * (isA ? 1.3 : 1), 0, 6.283);
      ctx.fillStyle = isA ? acc : `hsl(${hue(d.group)} ${dark ? 45 : 55}% ${dark ? 62 : 48}%)`;
      ctx.fill();
      if (isH) { ctx.lineWidth = 2 / T.k; ctx.strokeStyle = txt; ctx.stroke(); }
      if (isH || (showLabels && (T.k > 2 || (T.k > 1.2 && d.deg > 8) || (T.k > 0.7 && d.deg > 25) || isA))) {
        ctx.fillStyle = txt; ctx.fillText(d.name, d.x, d.y + radius(d) + 11 / Math.sqrt(T.k));
      }
    }
    ctx.restore();
  }
  const pt = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  const world = ([x, y]) => [(x - T.x - canvas.clientWidth / 2) / T.k, (y - T.y - canvas.clientHeight / 2) / T.k];
  const hit = (e) => { const [wx, wy] = world(pt(e)); return sim.find(wx, wy, 12 / T.k); };

  const zoom = d3.zoom().scaleExtent([0.15, 8])
    .filter((e) => (e.type === 'wheel' || (e.type !== 'dblclick' && !hit(e))))
    .on('zoom', (e) => { T = e.transform; draw(); });
  d3.select(canvas).call(zoom);
  d3.select(canvas).call(d3.drag().container(canvas)
    .subject((e) => { const n = hit(e.sourceEvent); return n || null; })
    .on('start', (e) => { if (!e.active) sim.alphaTarget(0.3).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
    .on('drag', (e) => { const [wx, wy] = world(pt(e.sourceEvent)); e.subject.fx = wx; e.subject.fy = wy; })
    .on('end', (e) => { if (!e.active) sim.alphaTarget(0); e.subject.fx = null; e.subject.fy = null; }));
  canvas.addEventListener('mousemove', (e) => { const n = hit(e) || null; if (n !== hover) { hover = n; canvas.style.cursor = n ? 'pointer' : 'default'; draw(); } });
  canvas.addEventListener('click', (e) => { const n = hit(e); if (n) openNote(n.id, { newTab: e.ctrlKey || e.metaKey }); });
  $('#g-local').onchange = (e) => { S.graphLocal = e.target.checked; build(); };
  $('#g-labels').onchange = draw;
  new ResizeObserver(resize).observe(wrap);
  build(); resize();
}

/* ---------- quick switcher ---------- */
function fuzzy(q, s) {
  q = q.toLowerCase(); s = s.toLowerCase();
  let i = 0, score = 0, last = -1;
  for (const ch of q) { const j = s.indexOf(ch, i); if (j < 0) return -1; score += (j === last + 1 ? 3 : 1) - j * 0.01; last = j; i = j + 1; }
  return score + (s.includes(q) ? 20 : 0);
}
function quickSwitcher() {
  const root = $('#modal-root');
  root.innerHTML = '<div class="scrim"><div class="modal"><input placeholder="Najít poznámku…" spellcheck="false"><div class="list"></div><div class="foot"><span>↑↓ vybrat</span><span>↵ otevřít</span><span>Ctrl+↵ nový tab</span><span>Esc zavřít</span></div></div></div>';
  const inp = $('input', root), list = $('.list', root);
  let items = [], sel = 0;
  const close = () => { root.innerHTML = ''; };
  const draw = () => {
    list.innerHTML = '';
    items.forEach((p, i) => {
      const d = document.createElement('div'); d.className = 'it' + (i === sel ? ' sel' : '');
      d.innerHTML = `<span>${esc(nameOf(p))}</span><span class="p">${esc(dirOf(p))}</span>`;
      d.onclick = (e) => { close(); openNote(p, { newTab: e.ctrlKey }); };
      list.append(d);
    });
    list.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
  };
  const refresh = () => {
    const q = inp.value.trim();
    items = (q
      ? S.notes.map((n) => [n.path, Math.max(fuzzy(q, nameOf(n.path)) * 2, fuzzy(q, n.path))]).filter((x) => x[1] >= 0).sort((a, b) => b[1] - a[1]).map((x) => x[0])
      : S.notes.slice().sort((a, b) => b.mtime - a.mtime).map((n) => n.path)).slice(0, 50);
    sel = 0; draw();
  };
  inp.oninput = refresh;
  inp.onkeydown = (e) => {
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, items.length - 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); draw(); }
    else if (e.key === 'Enter' && items[sel]) { const p = items[sel]; close(); openNote(p, { newTab: e.ctrlKey || e.metaKey }); }
  };
  $('.scrim', root).onmousedown = (e) => { if (e.target.classList.contains('scrim')) close(); };
  refresh(); inp.focus();
}

/* ---------- resizers + shortcuts ---------- */
function initResizers() {
  const set = (v, px) => document.documentElement.style.setProperty(v, px + 'px');
  set('--left-w', lsGet('leftW', 280)); set('--right-w', lsGet('rightW', 280));
  for (const [id, v, key, dir] of [['#rz-left', '--left-w', 'leftW', 1], ['#rz-right', '--right-w', 'rightW', -1]]) {
    const el = $(id);
    el.addEventListener('mousedown', (e) => {
      e.preventDefault(); el.classList.add('drag');
      const startX = e.clientX, start = parseInt(getComputedStyle(document.documentElement).getPropertyValue(v));
      const mv = (m) => set(v, Math.max(180, Math.min(600, start + (m.clientX - startX) * dir)));
      const up = () => { el.classList.remove('drag'); lsSet(key, parseInt(getComputedStyle(document.documentElement).getPropertyValue(v))); removeEventListener('mousemove', mv); removeEventListener('mouseup', up); };
      addEventListener('mousemove', mv); addEventListener('mouseup', up);
    });
  }
}
addEventListener('keydown', (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === 'o') { e.preventDefault(); quickSwitcher(); }
  else if (mod && e.key.toLowerCase() === 'g') { e.preventDefault(); openGraph(); }
  else if (mod && e.shiftKey && e.key.toLowerCase() === 'f') { e.preventDefault(); S.leftMode = 'search'; S.noLeft = false; applyLayout(); renderLeft(); renderRibbon(); setTimeout(() => $('#left .searchbox input')?.focus(), 0); }
  else if (mod && e.key.toLowerCase() === 'w') { if (S.active) { e.preventDefault(); closeTab(S.active); } }
});

function renderAll() { renderRibbon(); renderTabs(); renderLeft(); renderPane(); }

async function init() {
  applyTheme(); applyLayout(); initResizers();
  try {
    const r = await fetch('/data/vault.json');
    if (r.ok && (r.headers.get('content-type') || '').includes('json')) {
      DB = await r.json();
      searchCore = await import('/search-core.js');
    }
  } catch { /* live mode */ }
  const idx = await api('/api/index');
  S.notes = idx.notes; S.vault = idx.vault; S.noteSet = new Set(idx.notes.map((n) => n.path));
  document.title = idx.vault + ' – Vault';
  S.tabs = S.tabs.filter((t) => t.kind === 'graph' || S.noteSet.has(t.path));
  if (!tabById(S.active)) S.active = S.tabs[0]?.id || null;
  const hash = decodeURIComponent(location.hash.slice(1));
  if (hash && S.noteSet.has(hash)) { openNote(hash); return; }
  renderAll();
}
init().catch((e) => { document.body.innerHTML = `<pre style="padding:20px;color:#e93147">Chyba: ${esc(e.message)}</pre>`; });
