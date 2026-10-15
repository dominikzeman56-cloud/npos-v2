// Shared top bar for the standalone pages (Dashboard, Build Sheet, Presety, Co dál?): one brand, one nav, active tab, skin switch.
// Inserted synchronously as the first element of <body>; pages keep binding their own #skin handler (it is idempotent).
(function () {
  'use strict';
  var TABS = [
    ['/dashboard.html', 'Dashboard'], ['/buildsheet.html', 'Build Sheet'], ['/presets.html', 'Presety'], ['/dal.html', 'Co dál?'], ['/', 'Kánon'],
  ];
  var path = location.pathname.replace(/\/index\.html$/, '/');
  var cur = (TABS.filter(function (t) { return t[0] === path; })[0] || [])[1] || '';
  var css = document.createElement('style');
  css.textContent =
    '#topbar{position:sticky;top:0;z-index:20;display:flex;align-items:stretch;gap:6px;height:52px;padding:0 14px;padding-top:env(safe-area-inset-top);box-sizing:content-box;background:var(--bg2);border-bottom:1px solid var(--border);box-shadow:0 1px 0 rgba(255,255,255,.03),0 4px 18px rgba(0,0,0,.25)}' +
    '#topbar .tb-brand{display:flex;align-items:center;gap:8px;margin-right:10px;font-family:var(--font-mono,ui-monospace,Consolas,monospace);font-weight:700;letter-spacing:.12em;font-size:13px;color:var(--sam-green,#3eea9a);text-decoration:none;white-space:nowrap}' +
    '#topbar .tb-brand i{width:8px;height:8px;border-radius:50%;background:var(--sam-green,#3eea9a);box-shadow:0 0 8px var(--sam-green,#3eea9a)}' +
    '#topbar nav{display:flex;align-items:stretch;gap:2px;overflow-x:auto;scrollbar-width:none;min-width:0}' +
    '#topbar nav::-webkit-scrollbar{display:none}' +
    '#topbar nav a{display:flex;align-items:center;padding:0 12px;color:var(--muted);text-decoration:none;font-weight:600;font-size:14px;letter-spacing:.04em;white-space:nowrap;border-bottom:2px solid transparent;margin-bottom:-1px}' +
    '#topbar nav a:hover{color:var(--text);background:var(--hover)}' +
    '#topbar nav a[aria-current=page]{color:var(--text);border-bottom-color:var(--sam-green,#3eea9a)}' +
    '#topbar .tb-end{margin-left:auto;display:flex;align-items:center;gap:10px}' +
    '#topbar .tb-mod{font-family:var(--font-mono,ui-monospace,monospace);font-size:11px;letter-spacing:.1em;color:var(--muted);white-space:nowrap}' +
    '#topbar select{background:var(--bg1);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 9px;font:inherit;font-size:13px;min-height:34px;cursor:pointer}' +
    '#topbar a:focus-visible,#topbar select:focus-visible{outline:2px solid var(--link);outline-offset:-2px}' +
    '@media (max-width:760px){#topbar .tb-mod{display:none}#topbar .tb-brand span{display:none}#topbar{padding-left:10px;padding-right:10px}}';
  document.head.appendChild(css);
  var bar = document.createElement('header');
  bar.id = 'topbar';
  bar.innerHTML =
    '<a class="tb-brand" href="/dashboard.html" aria-label="NPOS/CTRL, Dashboard"><i></i><span>NPOS/CTRL</span></a>' +
    '<nav aria-label="Hlavní navigace">' + TABS.map(function (t) { return '<a href="' + t[0] + '"' + (t[1] === cur ? ' aria-current="page"' : '') + '>' + t[1] + '</a>'; }).join('') + '</nav>' +
    '<div class="tb-end"><span class="tb-mod">MODULE // ' + (cur || 'VAULT').toUpperCase() + '</span>' +
    '<select id="skin" aria-label="Vzhled (skin)"><option value="samurai">Samurai</option><option value="dark">Tmavý</option><option value="light">Světlý</option></select></div>';
  document.body.insertBefore(bar, document.body.firstChild);
})();
