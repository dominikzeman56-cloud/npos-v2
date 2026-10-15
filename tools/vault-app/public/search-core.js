// Full-text search over note objects {path, name, body, tags}. Shared by the live server (Node) and the static client (browser).
export function search(notes, q) {
  const tagM = q.match(/\btag:(\S+)/i);
  const tag = tagM ? tagM[1].replace(/^#/, '').toLowerCase() : null;
  const terms = q.replace(/\btag:\S+/gi, '').toLowerCase().split(/\s+/).filter(Boolean);
  const res = [];
  for (const n of notes) {
    if (tag && !n.tags.some((t) => t.toLowerCase() === tag || t.toLowerCase().startsWith(tag + '/'))) continue;
    const pl = n.path.toLowerCase();
    const bl = n.body.toLowerCase();
    let score = 0, ok = true, firstHit = -1;
    for (const t of terms) {
      const inPath = pl.includes(t);
      const pos = bl.indexOf(t);
      if (!inPath && pos < 0) { ok = false; break; }
      if (inPath) score += n.name.toLowerCase().includes(t) ? 10 : 4;
      if (pos >= 0) {
        if (firstHit < 0) firstHit = pos;
        let c = 0, i = pos;
        while (i >= 0 && c < 20) { c++; i = bl.indexOf(t, i + t.length); }
        score += Math.min(c, 20);
      }
    }
    if (!ok) continue;
    let snippet;
    if (firstHit >= 0) {
      const s = Math.max(0, firstHit - 50);
      snippet = n.body.slice(s, firstHit + 130).replace(/\s+/g, ' ');
    } else snippet = n.body.slice(0, 140).replace(/\s+/g, ' ');
    res.push({ path: n.path, score: score + (tag ? 1 : 0), snippet });
  }
  res.sort((a, b) => b.score - a.score);
  return { terms, results: res.slice(0, 80), total: res.length };
}
