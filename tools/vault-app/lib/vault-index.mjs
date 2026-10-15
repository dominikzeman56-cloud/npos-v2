// Shared vault indexer: used by the live server and by the static exporter.
import fs from 'node:fs/promises';
import path from 'node:path';

export const DEFAULT_IGNORE = ['.obsidian', '.git', '.trash', '.smart-env', '.raw', '.vault-meta', 'node_modules'];

export const baseName = (rel) => rel.split('/').pop().replace(/\.md$/i, '');
export const dirName = (rel) => (rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '');

async function walk(dir, rel, ignore, out) {
  let ents;
  try { ents = await fs.readdir(dir, { withFileTypes: true }); } catch { return; }
  for (const e of ents) {
    if (ignore.has(e.name)) continue;
    const r = rel ? rel + '/' + e.name : e.name;
    if (e.isDirectory()) await walk(path.join(dir, e.name), r, ignore, out);
    else if (e.isFile()) out.push(r);
  }
}

function stripCode(text) {
  return text
    .replace(/(^|\n)(```|~~~)[^\n]*\n[\s\S]*?\n\2[^\n]*(?=\n|$)/g, '$1')
    .replace(/`[^`\n]*`/g, '');
}

const unq = (s) => s.replace(/^(['"])(.*)\1$/, '$2');

export function parseFm(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/);
  if (!m) return { fm: {}, body: raw };
  const fm = {};
  let key = null;
  for (const line of m[1].split(/\r?\n/)) {
    let mm;
    if ((mm = line.match(/^([^\s:#][^:]*):\s*(.*)$/))) {
      key = mm[1].trim();
      const v = mm[2].trim();
      if (v === '') fm[key] = [];
      else if (v.startsWith('[') && v.endsWith(']'))
        fm[key] = v.slice(1, -1).split(',').map((s) => unq(s.trim())).filter(Boolean);
      else fm[key] = unq(v);
    } else if ((mm = line.match(/^\s*-\s+(.*)$/)) && key) {
      if (!Array.isArray(fm[key])) fm[key] = fm[key] ? [fm[key]] : [];
      fm[key].push(unq(mm[1].trim()));
    }
  }
  return { fm, body: raw.slice(m[0].length) };
}

export function normPosix(p) {
  const out = [];
  for (const part of p.split('/')) {
    if (part === '..') out.pop();
    else if (part && part !== '.') out.push(part);
  }
  return out.join('/');
}

function resolveLink(idx, target, from) {
  const t = target.replace(/\\/g, '/').replace(/^\/+/, '').toLowerCase();
  if (!t) return null;
  const cands = t.endsWith('.md') ? [t] : [t + '.md', t];
  for (const c of cands) {
    let hits;
    if (c.includes('/')) hits = idx.rels.filter((r) => { const l = r.toLowerCase(); return l === c || l.endsWith('/' + c); });
    else hits = idx.byFile.get(c) || [];
    if (hits.length) {
      const fromDir = dirName(from);
      return hits.slice().sort((a, b) =>
        (dirName(a) === fromDir ? 0 : 1) - (dirName(b) === fromDir ? 0 : 1) || a.length - b.length)[0];
    }
  }
  return null;
}

/**
 * opts.vault     absolute dir to index
 * opts.ignore    Set of dir/file names skipped at any depth
 * opts.include   (rel) => bool, extra file filter (e.g. extension allowlist)
 * opts.skipNote  (note) => bool, drop a parsed note (e.g. frontmatter `share: false`)
 */
export async function buildIndex({ vault, ignore = new Set(DEFAULT_IGNORE), include = null, skipNote = null }) {
  let rels = [];
  await walk(vault, '', ignore, rels);
  if (include) rels = rels.filter(include);

  const notes = new Map();
  await Promise.all(rels.filter((r) => /\.md$/i.test(r)).map(async (r) => {
    const abs = path.join(vault, r);
    try {
      const [raw, st] = await Promise.all([fs.readFile(abs, 'utf8'), fs.stat(abs)]);
      const { fm, body } = parseFm(raw);
      const n = { path: r, name: baseName(r), mtime: st.mtimeMs, size: st.size, fm, body };
      if (!skipNote || !skipNote(n)) notes.set(r, n);
    } catch { /* unreadable file: skip */ }
  }));
  rels = rels.filter((r) => !/\.md$/i.test(r) || notes.has(r));

  const byFile = new Map();
  for (const r of rels) {
    const k = r.split('/').pop().toLowerCase();
    if (!byFile.has(k)) byFile.set(k, []);
    byFile.get(k).push(r);
  }
  const idx = { vault, rels, byFile, notes, out: new Map(), backlinks: new Map(), tags: new Map() };

  for (const n of notes.values()) {
    const clean = stripCode(n.body);
    const links = {};
    const outgoing = [];
    for (const m of clean.matchAll(/(!?)\[\[([^\]\n]+?)\]\]/g)) {
      const target = m[2].split('|')[0].split('#')[0].split('^')[0].trim();
      if (!target) continue;
      if (!(target in links)) links[target] = resolveLink(idx, target, n.path);
      outgoing.push({ target, resolved: links[target], embed: !!m[1] });
    }
    for (const m of clean.matchAll(/\[[^\]]*\]\(([^)\s]+?\.md)(?:#[^)]*)?\)/gi)) {
      if (/^[a-z]+:/i.test(m[1])) continue;
      let p; try { p = decodeURIComponent(m[1]); } catch { p = m[1]; }
      const rel = normPosix(dirName(n.path) + '/' + p);
      outgoing.push({ target: p, resolved: notes.has(rel) ? rel : null, embed: false });
    }
    n.links = links;
    idx.out.set(n.path, outgoing);

    const tags = new Set();
    const fmTags = n.fm.tags ?? n.fm.tag;
    for (const t of Array.isArray(fmTags) ? fmTags : typeof fmTags === 'string' ? fmTags.split(/[,\s]+/) : [])
      if (t) tags.add(t.replace(/^#/, ''));
    for (const m of clean.matchAll(/(?:^|\s)#([\p{L}\p{N}_\-/]+)/gu))
      if (!/^\d+$/.test(m[1])) tags.add(m[1]);
    n.tags = [...tags];
    for (const t of n.tags) {
      if (!idx.tags.has(t)) idx.tags.set(t, []);
      idx.tags.get(t).push(n.path);
    }
  }
  for (const [from, outs] of idx.out) {
    const seen = new Set();
    for (const o of outs) {
      if (!o.resolved || o.resolved === from || seen.has(o.resolved)) continue;
      seen.add(o.resolved);
      if (!idx.backlinks.has(o.resolved)) idx.backlinks.set(o.resolved, []);
      idx.backlinks.get(o.resolved).push(from);
    }
  }
  return idx;
}

/* ---- API payloads (identical for live server and static export) ---- */

export const indexPayload = (idx) => ({
  vault: path.basename(idx.vault),
  notes: [...idx.notes.values()].map((n) => ({ path: n.path, mtime: n.mtime, tags: n.tags })),
});

export const notePayload = (idx, n) => ({
  path: n.path, name: n.name, fm: n.fm, body: n.body, mtime: n.mtime, tags: n.tags, links: n.links,
  backlinks: idx.backlinks.get(n.path) || [],
  outgoing: idx.out.get(n.path) || [],
});

export const tagsPayload = (idx) =>
  [...idx.tags].map(([tag, paths]) => ({ tag, count: paths.length })).sort((a, b) => b.count - a.count);

export function graphPayload(idx) {
  const deg = new Map();
  const edges = new Set();
  for (const [from, outs] of idx.out)
    for (const o of outs)
      if (o.resolved && o.resolved !== from && idx.notes.has(o.resolved)) {
        edges.add(from + '\n' + o.resolved);
        deg.set(from, (deg.get(from) || 0) + 1);
        deg.set(o.resolved, (deg.get(o.resolved) || 0) + 1);
      }
  return {
    nodes: [...idx.notes.values()].map((n) => ({ id: n.path, name: n.name, group: n.path.includes('/') ? n.path.split('/')[0] : '·', deg: deg.get(n.path) || 0 })),
    links: [...edges].map((e) => e.split('\n')),
  };
}
