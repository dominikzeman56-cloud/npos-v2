// Stránka generátoru: mluví jen s místním serverem (node server.mjs). Na statickém webu (Vercel) endpointy nejsou a stránka to řekne.
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const sk = $('#skin');
if (sk) {
  try { sk.value = JSON.parse(localStorage.getItem('vault.skin')) || 'samurai'; } catch { /* výchozí */ }
  sk.addEventListener('change', () => { try { localStorage.setItem('vault.skin', JSON.stringify(sk.value)); } catch { /* soukromý režim */ } document.documentElement.dataset.theme = sk.value; });
}

async function init() {
  const body = $('#stateBody');
  let st;
  try {
    const r = await fetch('/api/generator/status', { headers: { 'X-NPOS': '1' } });
    if (!r.ok) throw new Error(String(r.status));
    st = await r.json();
  } catch {
    body.innerHTML = '<span class="warn">Generátor běží jen v místním serveru.</span> Spusť na svém počítači <code>node tools/vault-app/server.mjs</code> a otevři <code>http://127.0.0.1:4747/generator.html</code>. Na sdílené kopii webu není, protože zapisuje soubory na tvůj disk.';
    return;
  }
  if (!st.ready) {
    body.innerHTML = `<span class="warn">${esc(st.note || 'Generátor není nastavený.')}</span><pre>NPOS_SERUM_PRESETS=&lt;složka s Serum 2 presety&gt;\nNPOS_SERUM_OUT=&lt;složka, kam se uloží výsledek&gt;</pre>Ulož to do <code>tools/vault-app/.env.local</code> (je mimo git) a restartuj server. Potřebuješ Python 3.12 s balíčkem <code>zstandard</code>.`;
    return;
  }
  const roles = Object.entries(st.roles).sort((a, b) => b[1] - a[1]);
  const total = roles.reduce((s, [, n]) => s + n, 0);
  body.innerHTML = `<span class="ok">Připraveno.</span> ${total} presetů ve složce <code>${esc(st.roots.join('; '))}</code>, výstup do <code>${esc(st.out)}</code>.`;
  $('#role').innerHTML = roles.map(([r, n]) => `<option value="${esc(r)}">${esc(r)} (${n})</option>`).join('');
  $('#seed').value = Math.floor(Math.random() * 1000);
  $('#form').hidden = false;
}

$('#go').addEventListener('click', async () => {
  const btn = $('#go'), res = $('#res');
  btn.disabled = true; res.innerHTML = 'Generuju…';
  try {
    const r = await fetch('/api/generator/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-NPOS': '1' },
      body: JSON.stringify({ role: $('#role').value, n: +$('#n').value, mutate: +$('#mutate').value, seed: +$('#seed').value, spread: +$('#spread').value, check: $('#check').checked }),
    });
    const d = await r.json();
    if (!r.ok) { res.innerHTML = `<span class="warn">${esc(d.error || 'Chyba ' + r.status)}</span>`; return; }
    const rej = Object.entries(d.rejected || {});
    res.innerHTML = `<p class="ok">Vzniklo ${d.files.length} z ${d.requested} souborů.</p><ul>${d.files.map((f) => `<li><code>${esc(f.file)}</code>: ${f.mutations} změn, z <code>${esc(f.derived_from)}</code></li>`).join('')}</ul>` +
      (rej.length ? `<p class="warn">Zahozeno: ${esc(rej.map(([k, v]) => k + ' ' + v).join(', '))}</p>` : '') +
      (d.message ? `<p class="warn">${esc(d.message)}</p>` : '') +
      '<p>V Serum 2 je najdeš ve složce výstupu (v prohlížeči presetů obnov seznam). Poslechem rozhodni, jestli stojí za to.</p>';
    $('#seed').value = +$('#seed').value + 1;
  } catch (e) {
    res.innerHTML = `<span class="warn">Nepodařilo se: ${esc(e.message)}</span>`;
  } finally { btn.disabled = false; }
});

init();
