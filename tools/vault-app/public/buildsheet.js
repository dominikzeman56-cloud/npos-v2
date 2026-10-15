// Build Sheet: pre-production brief for a track, stored only in this browser (localStorage 'vault.build').
// "Propsat do Dashboardu" copies title/tempo/key/goal/reference/bass into the Dashboard's current track ('vault.dash').
'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lsGet = (k, d) => { try { const v = localStorage.getItem('vault.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('vault.' + k, JSON.stringify(v)); return true; } catch { return false; } };

// Archetypes from the canon (20 Basa, kap. 3). Candidates (hypothesis) are marked; the page does not claim more than the canon does.
const ARCH = [
  ['', '— nevybráno —', ''],
  ['detuned-unison-reese', 'Detunovaný reese (fázový)', '#1 · naměřeno'],
  ['fm-distorted-body', 'FM tělo + distorze', '#2 · naměřeno'],
  ['grid-locked-filter-growl', 'Growl zamčený do mřížky', '#3 · odhad'],
  ['slow-grid-growl', 'Pomalý growl z harmonických', '#4 · naměřeno'],
  ['clean-sub-sine', 'Čistý sub', '#5 · naměřeno'],
  ['multi-pitch-reese', 'Multi-pitch reese (kandidát)', '#6 · naměřeno'],
  ['wt-detuned-saw', 'Wavetable z detunované saw (kandidát)', '#7 · naměřeno'],
  ['lfo-reese', 'LFO reese bez detune a FM (kandidát)', '#8 · naměřeno'],
  ['roar', 'Roar, pitch obálka (kandidát)', '#9 · naměřeno'],
  ['pitch-bend-womwom', 'Pitch-bend „wom-wom“', '#10 · naměřeno'],
  ['stab-accent', 'Stab accent (vrstva na reese)', '#11 · naměřeno'],
  ['switch-bass', 'Switch bass', '#13 · naměřeno'],
  ['osc-warp-body', 'Tělo z warpu jiným osc (kandidát)', '#16 · hypotéza'],
  ['other', 'Jiné', ''],
];
const FIELDS = {
  'g-proj': [['name', 'Název tracku'], ['tempo', 'Tempo (BPM)'], ['key', 'Tónina'], ['date', 'Datum', 'date'], ['artist', 'Autor'], ['version', 'Verze']],
  'g-mood': [['mood', 'Nálada'], ['energy', 'Energie (1–10)', 'number'], ['idea', 'Hlavní nápad / hook', 'ta'], ['never', 'Co se NESMÍ stát', 'ta']],
  'g-ref': [['ref1', 'Reference 1'], ['ref2', 'Reference 2'], ['ref3', 'Reference 3']],
  'g-drums': [['kick', 'Kick'], ['snare', 'Snare'], ['groove', 'Groove / bicí', 'ta']],
  'g-arr': [['dropA', 'Role Dropu A'], ['brk', 'Role breaku'], ['dropB', 'Čím se liší Drop B']],
  'g-goal': [['goal', 'Dnešní cíl', 'ta'], ['export', 'Další výstup (export)']],
};
let B = Object.assign({ f: {}, layers: [] }, lsGet('build', {}));
let PRESETS = [];
const save = () => { $('#st').textContent = lsSet('build', B) ? 'uloženo jen v tomhle prohlížeči' : 'nelze uložit (soukromý režim?)'; };

function renderFields() {
  for (const [gid, list] of Object.entries(FIELDS)) {
    $('#' + gid).innerHTML = list.map(([k, l, t]) => {
      const v = esc(B.f[k] || '');
      const input = t === 'ta' ? `<textarea id="f-${k}" data-k="${k}">${v}</textarea>` : `<input id="f-${k}" data-k="${k}" type="${t || 'text'}" value="${v}" autocomplete="off">`;
      return `<div class="f${t === 'ta' ? '' : ''}" style="${t === 'ta' ? 'grid-column: span 3' : ''}"><label for="f-${k}">${esc(l)}</label>${input}</div>`;
    }).join('');
  }
  const sel = $('#bass');
  sel.innerHTML = ARCH.map(([id, l]) => `<option value="${id}">${esc(l)}</option>`).join('');
  sel.value = B.f.bass || ''; $('#bassNote').value = B.f.bassNote || '';
  hint();
}
function hint() {
  const a = ARCH.find((x) => x[0] === (B.f.bass || ''));
  $('#bassHint').innerHTML = a && a[0] ? `Kánon: ${esc(a[2])} · <a href="/#${encodeURIComponent('20 Basa.md')}::${encodeURIComponent('3. Archetypy basů')}">20 Basa, kap. 3</a>` : 'Archetypy jsou z kánonu (20 Basa, kap. 3).';
}
function renderLayers() {
  $('#lays').innerHTML = B.layers.length ? B.layers.map((l, i) => {
    const p = PRESETS.find((x) => x.name === l.preset);
    return `<div class="lay"><input data-i="${i}" data-k="name" value="${esc(l.name)}" placeholder="vrstva (sub, body, …)" aria-label="Vrstva">
      <input data-i="${i}" data-k="role" value="${esc(l.role)}" placeholder="role" aria-label="Role">
      <input data-i="${i}" data-k="preset" list="plist" value="${esc(l.preset)}" placeholder="preset z indexu (název)" aria-label="Preset">
      <input data-i="${i}" data-k="note" value="${esc(l.note)}" placeholder="poznámka" aria-label="Poznámka">
      <span>${p ? `<a class="go" href="/presets.html?id=${encodeURIComponent(p.id)}">stavba →</a>` : ''}<button class="btn" type="button" data-del="${i}" aria-label="Smazat vrstvu">×</button></span></div>`;
  }).join('') : '<div class="hint">Zatím žádná vrstva. Typicky: sub, body, movement, texture, drums.</div>';
}

function wire() {
  document.addEventListener('input', (e) => {
    const t = e.target;
    if (t.dataset.i != null) { B.layers[+t.dataset.i][t.dataset.k] = t.value; save(); if (t.dataset.k === 'preset') renderLayersKeepFocus(t); return; }
    if (t.dataset.k) { B.f[t.dataset.k] = t.value; save(); if (t.dataset.k === 'bass') hint(); }
  });
  $('#ladd').onclick = () => { B.layers.push({ name: '', role: '', preset: '', note: '' }); save(); renderLayers(); };
  $('#lays').onclick = (e) => { const b = e.target.closest('[data-del]'); if (b) { B.layers.splice(+b.dataset.del, 1); save(); renderLayers(); } };
  $('#push').onclick = () => {
    const D = Object.assign({ track: {}, notes: [], tasks: [], sessions: [] }, lsGet('dash', {}));
    D.track = Object.assign({}, D.track, {
      title: B.f.name || D.track.title || '', bpm: B.f.tempo || D.track.bpm || '', key: B.f.key || D.track.key || '',
      goal: B.f.goal || D.track.goal || '', reference: B.f.ref1 || D.track.reference || '', bass: (ARCH.find((a) => a[0] === B.f.bass) || [])[1] && B.f.bass ? ARCH.find((a) => a[0] === B.f.bass)[1] : D.track.bass || '',
    });
    $('#st').textContent = lsSet('dash', D) ? 'propsáno do Dashboardu' : 'nelze uložit';
  };
  $('#exp').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(B, null, 1)], { type: 'application/json' })); a.download = 'buildsheet.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
  $('#imp').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { const j = JSON.parse(await f.text()); if (!j || typeof j !== 'object') throw 0; B = Object.assign({ f: {}, layers: [] }, j); save(); renderFields(); renderLayers(); } catch { alert('Soubor se nepodařilo načíst (není to Build Sheet).'); }
    e.target.value = '';
  };
  const sk = $('#skin'); sk.value = lsGet('skin', 'samurai');
  sk.onchange = () => { lsSet('skin', sk.value); document.documentElement.dataset.theme = sk.value; };
}
// redraw layer rows but keep typing in the same field
function renderLayersKeepFocus(t) {
  const i = t.dataset.i, k = t.dataset.k, pos = t.selectionStart; renderLayers();
  const n = document.querySelector(`[data-i="${i}"][data-k="${k}"]`); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch { /* not a text input */ } }
}

(async () => {
  wire(); renderFields(); renderLayers();
  try {
    for (const u of ['/data/presets.json', '/api/presets']) { const r = await fetch(u); if (r.ok && (r.headers.get('content-type') || '').includes('json')) { PRESETS = (await r.json()).presets || []; break; } }
  } catch { /* works without the index */ }
  $('#plist').innerHTML = PRESETS.slice(0, 1500).map((p) => `<option value="${esc(p.name)}"></option>`).join('');
  renderLayers();
})();
