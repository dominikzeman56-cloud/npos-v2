// NPOS Variace — Max for Live MIDI Tool (Transformation): switch-upy vlastního riffu pro neurofunk / DnB.
// Vezme noty klipu (výběr) a vrátí jejich variaci. Bez dat z packů, jen pravidla: dá se sdílet.
// Typy: Konec (jiný konec fráze), Oktávy, Chroma (půltónové náběhy à la Ekwols), Ratchet, Drop 2 (mix, první fráze beze změny).
// Apply cycle: Live při každé změně knobu vrací původní noty, takže variace se vždy počítá z originálu.
// Běží i v Node (testy): Max části jsou chráněné `typeof outlet`.

"use strict";

var TYPES = ["Konec", "Oktávy", "Chroma", "Ratchet", "Drop 2"];
var PHRASES = [2, 4, 8]; // délka fráze v taktech (kde je „konec“)
var DEFAULT_SCALE = { root: 5, intervals: [0, 2, 3, 5, 7, 8, 10] };

function rng(seed) {
  var a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    var t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function inScale(pitch, scale) {
  return scale.intervals.indexOf((((pitch - scale.root) % 12) + 12) % 12) >= 0;
}

function stepScale(pitch, scale, dir) {
  var p = pitch + dir;
  for (var i = 0; i < 12 && !inScale(p, scale); i++) p += dir;
  return p;
}

function clampPitch(p) { return Math.max(0, Math.min(127, p)); }

function copyNote(n) {
  var o = {};
  for (var k in n) o[k] = n[k];
  return o;
}

function newNote(src, start, dur, pitch, vel) {
  // vložená nota: bez note_id, Live ji založí jako novou
  return { pitch: clampPitch(pitch), start_time: start, duration: dur, velocity: Math.max(1, Math.min(127, Math.round(vel))),
           mute: 0, probability: 1, velocity_deviation: 0, release_velocity: src.release_velocity || 64 };
}

function groups(notes) {
  // noty se stejným začátkem = jeden úder (akord se mění celý)
  var by = {}, keys = [];
  notes.forEach(function (n) {
    var k = Math.round(n.start_time * 1000) / 1000;
    if (!by[k]) { by[k] = []; keys.push(k); }
    by[k].push(n);
  });
  keys.sort(function (a, b) { return a - b; });
  return keys.map(function (k) { return { t: k, notes: by[k] }; });
}

function onBeat(t) { return Math.abs(t - Math.round(t)) < 1e-6; }

// ---------- typy ----------

function konec(notes, scale, r, amt, phraseBars, onlyFrom) {
  // poslední takt každé fráze: posledních 1–3 úderů jinak (stupeň vedle / oktáva / tónika), vysoko i náběh
  if (!notes.length) return notes;
  var origin = Math.floor(Math.min.apply(null, notes.map(function (n) { return n.start_time; })) / 4) * 4;
  var endT = Math.max.apply(null, notes.map(function (n) { return n.start_time + n.duration; }));
  var len = phraseBars * 4, out = notes.slice(), added = [];
  for (var b0 = origin; b0 < endT - 1e-6; b0 += len) {
    if (b0 + 1e-6 < (onlyFrom || origin)) continue;
    var last0 = b0 + len - 4;
    var gs = groups(out.filter(function (n) { return n.start_time >= last0 - 1e-6 && n.start_time < b0 + len - 1e-6; }));
    if (!gs.length) continue;
    var k = Math.min(gs.length, Math.max(1, Math.round(amt * 3)));
    for (var i = gs.length - k; i < gs.length; i++) {
      var op = Math.floor(r() * 4);
      gs[i].notes.forEach(function (n) {
        if (op === 0) n.pitch = clampPitch(stepScale(n.pitch, scale, 1));
        else if (op === 1) n.pitch = clampPitch(stepScale(n.pitch, scale, -1));
        else if (op === 2) n.pitch = clampPitch(n.pitch + (n.pitch < 60 ? 12 : -12));
        else { // na tóniku nejblíž
          var best = n.pitch;
          for (var d = 0; d <= 6; d++) {
            if ((((n.pitch - d - scale.root) % 12) + 12) % 12 === 0) { best = n.pitch - d; break; }
            if ((((n.pitch + d - scale.root) % 12) + 12) % 12 === 0) { best = n.pitch + d; break; }
          }
          n.pitch = clampPitch(best);
        }
      });
    }
    if (amt > 0.6) {
      // náběh: poslední úder zopakovat šestnáctinami do konce fráze, pokud je tam místo
      var lastG = gs[gs.length - 1], from = lastG.t + 0.25, stop = b0 + len;
      var free = !out.some(function (n) { return n.start_time > lastG.t + 1e-6 && n.start_time < stop - 1e-6; });
      if (free && stop - from >= 0.25 && stop - from <= 2) {
        lastG.notes.forEach(function (n) { n.duration = Math.min(n.duration, 0.25); });
        for (var t = from; t < stop - 1e-6; t += 0.25) {
          lastG.notes.forEach(function (n) { added.push(newNote(n, t, 0.25, n.pitch, (n.velocity || 100) - 15 + (t - from) * 20)); });
        }
      }
    }
  }
  return out.concat(added);
}

function oktavy(notes, scale, r, amt, onlyFrom) {
  // oktávový skok u části úderů; první doba taktu drží groove, takže zůstává
  groups(notes).forEach(function (g) {
    if (g.t + 1e-6 < (onlyFrom || 0)) return;
    if ((g.t % 4) < 1e-6) return;
    if (r() < amt * 0.5) {
      var up = g.notes[0].pitch < 60 ? 12 : (r() < 0.5 ? 12 : -12);
      g.notes.forEach(function (n) { n.pitch = clampPitch(n.pitch + up); });
    }
  });
  return notes;
}

function chroma(notes, scale, r, amt, onlyFrom) {
  // půltónový náběh šestnáctinu před tónem na době, ze strany předchozího tónu (Ekwols)
  var gs = groups(notes), added = [];
  for (var i = 1; i < gs.length; i++) {
    var a = gs[i - 1], b = gs[i];
    if (b.t - 0.25 + 1e-6 < (onlyFrom || 0) || !onBeat(b.t)) continue; // i náběh musí ležet v měněné části
    var pa = Math.min.apply(null, a.notes.map(function (n) { return n.pitch; }));
    var pb = Math.min.apply(null, b.notes.map(function (n) { return n.pitch; }));
    if (pa === pb || b.t - a.t < 0.5 || r() >= amt) continue;
    var at = b.t - 0.25;
    a.notes.forEach(function (n) { n.duration = Math.min(n.duration, at - n.start_time); });
    var src = b.notes[0];
    added.push(newNote(src, at, 0.25, pb + (pb > pa ? -1 : 1), (src.velocity || 100) - 12));
  }
  return notes.concat(added);
}

function ratchet(notes, scale, r, amt, onlyFrom) {
  // dlouhé tóny: druhá půlka rozsekaná na 1/16 (vysoko 1/32) s rostoucí velocity
  var added = [];
  notes.forEach(function (n) {
    if (n.start_time + 1e-6 < (onlyFrom || 0) || n.duration < 0.5 || r() >= amt) return;
    var step = amt > 0.75 ? 0.125 : 0.25;
    var half = Math.max(step, Math.floor(n.duration / 2 / step) * step);
    var from = n.start_time + n.duration - half;
    n.duration = from - n.start_time;
    for (var t = from, i = 0; t < from + half - 1e-6; t += step, i++) {
      added.push(newNote(n, t, step * 0.9, n.pitch, (n.velocity || 100) - 20 + i * 6));
    }
  });
  return notes.concat(added);
}

// ---------- vstup ----------

function transform(notes, context, p) {
  var scale = DEFAULT_SCALE;
  if (context && context.scale && context.scale.scale_intervals && context.scale.scale_intervals.length) {
    scale = { root: context.scale.root_note % 12, intervals: context.scale.scale_intervals.slice() };
  }
  var work = notes.map(copyNote);
  var amt = p.amount, phraseBars = PHRASES[p.phrase] || 4;
  var r = rng(p.seed * 131 + p.type * 977);
  var type = TYPES[p.type];
  if (type === "Konec") work = konec(work, scale, r, amt, phraseBars, null);
  else if (type === "Oktávy") work = oktavy(work, scale, r, amt, null);
  else if (type === "Chroma") work = chroma(work, scale, r, amt, null);
  else if (type === "Ratchet") work = ratchet(work, scale, r, amt, null);
  else if (type === "Drop 2") {
    // první fráze beze změny (drop 1), od druhé mix: jiný konec, trochu oktáv, náběhy, ratchet
    if (work.length) {
      var origin = Math.floor(Math.min.apply(null, work.map(function (n) { return n.start_time; })) / 4) * 4;
      var from = origin + phraseBars * 4;
      work = konec(work, scale, rng(p.seed * 131 + 1), amt, phraseBars, from);
      work = oktavy(work, scale, rng(p.seed * 131 + 2), amt * 0.5, from);
      work = chroma(work, scale, rng(p.seed * 131 + 3), amt * 0.6, from);
      work = ratchet(work, scale, rng(p.seed * 131 + 4), amt * 0.4, from);
    }
  }
  return work.filter(function (n) { return n.duration > 0.01; })
    .sort(function (a, b) { return a.start_time - b.start_time || a.pitch - b.pitch; });
}

// ---------- Max ----------

var params = { type: 0, amount: 0.5, seed: 1, phrase: 1 };
var context = null;
var clipNotes = null;

if (typeof outlet === "function") {
  inlets = 2;
  outlets = 2;
}

function type(v) { params.type = Math.max(0, Math.min(TYPES.length - 1, v | 0)); }
function amount(v) { params.amount = Math.max(0, Math.min(1, v / 100)); }
function seed(v) { params.seed = Math.max(1, v | 0); }
function phrase(v) { params.phrase = Math.max(0, Math.min(PHRASES.length - 1, v | 0)); }
function dice() {
  params.seed = 1 + Math.floor(Math.random() * 999);
  outlet(1, params.seed);
}

var got = [false, false];

function dictionary(name) {
  // noty i kontext v libovolném pořadí, transformuj až po obou (stejně jako NPOS Skeleton)
  var d = new Dict(name);
  var obj = JSON.parse(d.stringify());
  if (inlet === 1) context = obj;
  else clipNotes = obj.notes || [];
  got[inlet === 1 ? 1 : 0] = true;
  if (!(got[0] && got[1])) return;
  got = [false, false];
  var out = new Dict();
  out.parse(JSON.stringify({ notes: transform(clipNotes, context, params) }));
  outlet(0, "dictionary", out.name);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { transform: transform, TYPES: TYPES, PHRASES: PHRASES };
}
