// Shared "Co dál?" search used by the Co dál? page and the Dashboard, so both answer the same way.
// Keyword match over situation (weight 3) and steps/sources (weight 1); items of the current phase win ties.
(function () {
  'use strict';
  function words(q) { return String(q || '').toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(function (w) { return w.length > 2; }); }
  function search(items, query, phase, limit) {
    var ws = words(query);
    if (!ws.length) return [];
    var scored = items.map(function (it) {
      var sit = it.situation.toLowerCase(), hay = (it.situation + ' ' + it.steps.join(' ') + ' ' + it.sources.join(' ')).toLowerCase();
      var s = ws.reduce(function (a, w) { return a + (sit.indexOf(w) >= 0 ? 3 : 0) + (hay.indexOf(w) >= 0 ? 1 : 0); }, 0);
      return [s > 0 && phase && it.phase === phase ? s + 2 : s, it];
    }).filter(function (x) { return x[0] > 0; }).sort(function (a, b) { return b[0] - a[0]; });
    return scored.slice(0, limit || 50).map(function (x) { return x[1]; });
  }
  window.NposAdvisor = { search: search };
})();
