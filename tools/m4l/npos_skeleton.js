// NPOS Skeleton — Max for Live MIDI Tool (Generator) pro neurofunk / DnB.
// Bass, reese, sub a lead: skutečné čtyřtaktové fráze z packů (rytmus + výšky + délky drží pohromadě),
// převedené na stupně proti tónině z názvu souboru, transponované do tóniny klipu a opakované podle formy z dat.
// Pad: skutečné progrese s původním voicingem. Bicí a stab: banka taktů/dvoutaktů z referencí.
// Záložní cesta (role bez frází): náhodná procházka s harmonickým plánem = hypotéza, ne měření.
// Data: data/midi/_local/midi-model.json (tools/midi_model.py).
// Tento soubor je zdroj; build_amxd.py do něj vloží model a zabalí ho do .amxd (v8.codebox).
// Běží i v Node (testy): Max části jsou chráněné `typeof outlet`.

"use strict";

var MODEL = /*MODEL*/ null;

var ROLES = ["sub", "bass", "reese", "stab", "lead", "harmony", "kick", "snare", "hats", "drums"];
var ROLE_LABELS = ["Sub", "Bass", "Reese", "Stab", "Lead", "Pad", "Kick", "Snare", "Hats", "Drums"];
// pevná sůl seedu na roli: přidání role do menu nesmí změnit, co dá uložený seed u ostatních
var SALT = { sub: 0, bass: 1, stab: 2, lead: 3, harmony: 4, kick: 5, snare: 6, hats: 7, reese: 9 };
var VOICINGS = ["Auto", "Mono", "Kvinta", "Oktáva", "Akord", "Akord 9"];
var BAR_CHOICES = [0, 1, 2, 4, 8, 16]; // 0 = podle výběru v klipu
var BASE = { sub: 24, bass: 36, reese: 36, stab: 48, lead: 60, harmony: 48 }; // Live: C3 = 60
var HOLD = { sub: true, harmony: true }; // tyhle role drží do další noty vždycky
var DRUM_PITCH = { kick: 36, snare: 38, hats: 42 }; // Drum Rack: C1, D1, F#1
var DEFAULT_SCALE = { root: 5, intervals: [0, 2, 3, 5, 7, 8, 10] }; // F moll, když klip tóninu nemá
var DUR_CLASSES = [1, 2, 3, 4, 6, 8, 12, 16];

// ---------- náhoda (deterministická podle seedu) ----------

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

function pickWeighted(r, items, weights) {
  var tot = 0, i;
  for (i = 0; i < weights.length; i++) tot += weights[i];
  if (tot <= 0) return items[Math.floor(r() * items.length)];
  var x = r() * tot;
  for (i = 0; i < items.length; i++) {
    x -= weights[i];
    if (x <= 0) return items[i];
  }
  return items[items.length - 1];
}

// ---------- rytmus ----------

function onsetCount(rh) {
  var n = 0;
  for (var i = 0; i < rh.length; i++) if (rh.charAt(i) === "x") n++;
  return n;
}

function targetDensity(m, density) {
  // 0 → pod dolním kvartilem, 0.5 → medián, 1 → nad horním kvartilem
  var d = m.density;
  if (density <= 0.5) return d.q1 * 0.6 + (d.median - d.q1 * 0.6) * (density / 0.5);
  return d.median + (d.q3 * 1.4 - d.median) * ((density - 0.5) / 0.5);
}

function pickRhythm(r, m, density, bank, perBars, variation) {
  // bank = m.rhythms (takty) nebo m.rhythms2 (dvoutakty); cílová hustota se násobí počtem taktů.
  // Banka je seřazená podle četnosti: nízká Variace bere jen nejčastější grooovy (méně náhodné).
  bank = bank || m.rhythms;
  var target = targetDensity(m, density) * (perBars || 1);
  var lim = variation === undefined ? bank.length : Math.max(6, Math.round(bank.length * (0.25 + 0.75 * variation)));
  var items = [], w = [];
  for (var i = 0; i < Math.min(bank.length, lim); i++) {
    var rh = bank[i][0], c = bank[i][1];
    items.push(rh);
    // četnost lineárně: v referencích častý takt má vyhrávat (kick x.........x..... vs. four-on-the-floor)
    w.push(c * Math.exp(-Math.abs(onsetCount(rh) - target) / 1.2));
  }
  return pickWeighted(r, items, w);
}

function mutate(r, rh, m, amount) {
  // přepni pár šestnáctin podle naměřené pravděpodobnosti slotu; první doba zůstává
  var cells = rh.split("");
  var flips = Math.max(1, Math.round(amount * 4));
  for (var k = 0; k < flips; k++) {
    var i = 1 + Math.floor(r() * 15);
    var p = m.slot_prob[i];
    if (cells[i] === "x") { if (r() > p) cells[i] = "."; }
    else if (r() < p * 1.5) cells[i] = "x";
  }
  return cells.join("");
}

function barRhythms(r, m, bars, density, variation) {
  if (bars >= 2 && m.rhythms2 && m.rhythms2.length >= 8) return twoBarRhythms(r, m, bars, density, variation);
  // fráze A A A B (a v osmitaktí A A A B A A A C): jeden takt vzoru, variace na konci čtyřtaktí
  var a = pickRhythm(r, m, density, m.rhythms, 1, variation);
  var out = [];
  for (var b = 0; b < bars; b++) {
    var rh = a;
    if (b % 4 === 3) rh = r() < 0.5 ? mutate(r, a, m, 0.5 + variation) : pickRhythm(r, m, Math.min(1, density + 0.2), m.rhythms, 1, variation);
    else if (b > 0 && r() < variation * 0.5) rh = mutate(r, a, m, variation);
    out.push(rh);
  }
  return out;
}

function twoBarRhythms(r, m, bars, density, variation) {
  // dvoutaktová fráze z banky: A A' — variace jen ve druhém taktu na konci čtyřtaktí (první takt drží groove)
  var a = pickRhythm(r, m, density, m.rhythms2, 2, variation);
  var out = [];
  for (var u = 0; u * 2 < bars; u++) {
    var first = a.slice(0, 16), second = a.slice(16);
    if (u % 2 === 1) {
      second = r() < 0.5 ? mutate(r, second, m, 0.5 + variation) : pickRhythm(r, m, Math.min(1, density + 0.2), m.rhythms2, 2, variation).slice(16);
    } else if (u > 0 && r() < variation * 0.5) {
      second = mutate(r, second, m, variation);
    }
    out.push(first, second);
  }
  return out.slice(0, bars);
}

// ---------- výšky ----------

function inScale(pc, scale) {
  var rel = ((pc - scale.root) % 12 + 12) % 12;
  return scale.intervals.indexOf(rel) >= 0;
}

function degreeToSemis(scale, degree) {
  var n = scale.intervals.length;
  var oct = Math.floor(degree / n);
  var idx = ((degree % n) + n) % n;
  return scale.intervals[idx] + 12 * oct;
}

function planRoots(r, bars) {
  // kořen každého taktu jako stupeň stupnice; turnaround od 3. doby na konci čtyřtaktí
  var plan = [];
  for (var b = 0; b < bars; b++) plan.push({ root: 0, turn: null });
  for (b = 0; b < bars; b++) if (b % 4 === 3) plan[b].turn = [5, 6, 4, 6][Math.floor(r() * 4)];
  if (bars >= 8) plan[5].root = r() < 0.5 ? 5 : 6;
  return plan;
}

function nextPitch(r, m, scale, rootPitch, prev, lo, hi, chroma) {
  // lo..hi = povolené okno výšek; offsety a oktávový skok se měří od kořene taktu
  // chroma 0..1: povolí půltón mimo stupnici hned vedle předchozí noty (chromatický krok à la Ekwols)
  var offs = m.offsets || [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  var motion = m.motion || { repeat: 1, step: 0, mid: 0, leap: 0, octave: 0 };
  var kinds = ["repeat", "step", "mid", "leap", "octave"];
  if (prev === null) return rootPitch; // fráze začíná na kořeni taktu, ne náhodným tónem
  var kind = pickWeighted(r, kinds, kinds.map(function (k) { return motion[k]; }));
  var cands = [], w = [];
  for (var p = lo; p <= hi; p++) {
    var outside = !inScale(p % 12, scale);
    if (outside && !(chroma > 0 && prev !== null && Math.abs(p - prev) === 1)) continue;
    var off = ((p - rootPitch) % 12 + 12) % 12;
    var weight = outside ? 0.25 * chroma : offs[off] + 0.002;
    if (p >= rootPitch + 12) weight *= (m.octave_up || 0.05) * 2;
    if (prev !== null) {
      var d = Math.abs(p - prev);
      var k = d === 0 ? "repeat" : d <= 2 ? "step" : d <= 6 ? "mid" : d <= 11 ? "leap" : "octave";
      weight *= k === kind ? 1 : 0.08;
    }
    cands.push(p);
    w.push(weight);
  }
  return cands.length ? pickWeighted(r, cands, w) : rootPitch;
}

function voice(scale, pitch, mode, open) {
  // Hlas: tón -> noty akordu nad ním. Akordy se skládají ze stupnice klipu (terciové), mimo stupnici jen kvinta.
  // Tón melodie zůstává nejnižší (pitches[0]), legato se řídí podle něj.
  if (mode === "Mono") return [pitch];
  if (mode === "Kvinta") return [pitch, pitch + 7];
  if (mode === "Oktáva") return [pitch, pitch + 12];
  var rel = ((pitch % 12 - scale.root) % 12 + 12) % 12;
  var idx = scale.intervals.indexOf(rel);
  if (idx < 0) return [pitch, pitch + 7];
  var base = degreeToSemis(scale, idx);
  var third = degreeToSemis(scale, idx + 2) - base, fifth = degreeToSemis(scale, idx + 4) - base;
  // jako v packách: basový tón dole, akord nad ním otevřeně (open = bass/reese: tercie o oktávu výš)
  var lift = open ? 12 : 0;
  var out = [pitch, pitch + fifth, pitch + third + lift];
  if (mode === "Akord 9") {
    // moll akord dostane nonu (i m9, iv m9), dur akord septimu (bVI maj7, bVII7) — nejčastější v packách
    var ext = third === 3 ? degreeToSemis(scale, idx + 1) - base + 12 : degreeToSemis(scale, idx + 6) - base;
    out.push(pitch + ext + lift);
  }
  return out;
}

function voicingFor(role, choice) {
  if (VOICINGS[choice] !== "Auto") return VOICINGS[choice];
  return role === "stab" ? "Kvinta" : role === "harmony" ? "Akord" : "Mono";
}

function legatoDur(role, ev, next, legato) {
  // 50 % = délka jak je v datech (u frází přesně jako v packu). Níž kratší až staccato,
  // výš až k další notě a nakonec přesah 1/8 doby pro glide. Stejná výška se nikdy nepřekryje (Live by noty slil).
  var glide = next && next.pitches[0] !== ev.pitches[0];
  var dur;
  if (legato <= 0.5) {
    var short = Math.min(ev.dur0, Math.max(0.125, ev.gap * 0.5));
    dur = short + (ev.dur0 - short) * (legato / 0.5);
  } else {
    var f = (legato - 0.5) / 0.5;
    var full = ev.gap + (glide ? 0.125 : 0);
    dur = ev.dur0 + (Math.max(full, ev.dur0) - ev.dur0) * f;
  }
  if (next && !glide) dur = Math.min(dur, ev.gap);
  if (legato < 0.5) dur = Math.min(dur, Math.max(0.0625, ev.gap - 0.0625)); // pod 50 % vždy mezera
  return Math.max(0.0625, dur);
}

// ---------- generátor ----------

function pickDur(r, m) {
  var ks = DUR_CLASSES, w = ks.map(function (k) { return m.dur16[String(k)] || 0; });
  return pickWeighted(r, ks, w) * 0.25;
}

function velocity(r, m, slot) {
  var v = slot % 4 === 0 ? m.vel.on : m.vel.off;
  if (slot === 0) v += 8;
  return Math.max(1, Math.min(127, Math.round(v + (r() - 0.5) * 10)));
}

function genRole(role, p, scale, start, bars, hplan) {
  var m = MODEL.roles[role];
  if (!m || !m.enough) return [];
  var r = rng(p.seed * 31 + SALT[role] * 7919);
  var rhythms = barRhythms(r, m, bars, p.density, p.variation);
  var notes = [];
  var drum = DRUM_PITCH[role];
  var plan = planRoots(r, bars);
  var prev = null;
  var events = []; // pitched role: nejdřív výšky, délky až podle další noty (legato)
  var onsets = []; // všechny nástupy fráze v dobách: mezera do další noty i přes hranici taktu
  for (var ob = 0; ob < bars; ob++)
    for (var oi = 0; oi < 16; oi++) if (rhythms[ob].charAt(oi) === "x") onsets.push(ob * 4 + oi * 0.25);
  var k = 0;
  for (var b = 0; b < bars; b++) {
    var rh = rhythms[b];
    var slots = [];
    for (var i = 0; i < 16; i++) if (rh.charAt(i) === "x") slots.push(i);
    for (var j = 0; j < slots.length; j++) {
      var s = slots[j];
      var t = b * 4 + s * 0.25;
      var gap = (k + 1 < onsets.length ? onsets[k + 1] : bars * 4) - t;
      k++;
      var vel = velocity(r, m, s);
      if (drum !== undefined) {
        notes.push({ pitch: drum, start_time: start + t, duration: 0.25, velocity: vel });
        continue;
      }
      var degree = plan[b].turn !== null && s >= 8 ? plan[b].turn : plan[b].root;
      var tonic = BASE[role] + scale.root + p.octave * 12;
      var rootPitch = hplan ? tonic + hplan.at(t).root : tonic + degreeToSemis(scale, degree);
      var line;
      if (role === "harmony") {
        line = rootPitch; // pad = akord na kořeni taktu
      } else if (role === "sub") {
        // sub drží jednu oktávu od tóniky klipu: kořen taktu se do ní přehodí, žádné skoky nahoru
        var rootSub = tonic + ((rootPitch - tonic) % 12 + 12) % 12;
        line = prev = nextPitch(r, m, scale, rootSub, prev, tonic, tonic + 11, 0);
      } else {
        // basa, reese a stab max oktávu nad kořen, lead má víc prostoru; reese s Variací chromaticky
        var chroma = role === "reese" ? p.variation : 0;
        var hi = role === "lead" ? 19 : role === "reese" ? 7 : 12; // reese drží střed, vysoko ztrácí váhu
        line = prev = nextPitch(r, m, scale, rootPitch, prev, rootPitch - 5, rootPitch + hi, chroma);
      }
      var mode = role === "sub" ? "Mono" : voicingFor(role, p.voicing);
      events.push({ t: t, gap: gap, vel: vel, dur0: HOLD[role] ? gap : Math.min(gap, pickDur(r, m)), pitches: voice(scale, line, mode, BASE[role] <= 36) });
    }
  }
  for (var e = 0; e < events.length; e++) {
    var ev = events[e];
    var dur = legatoDur(role, ev, events[e + 1], p.legato);
    ev.pitches.forEach(function (pt) {
      notes.push({ pitch: pt, start_time: start + ev.t, duration: dur, velocity: ev.vel });
    });
  }
  if (role === "snare" && bars >= 4 && p.variation >= 0.5) {
    // fill v posledním taktu (pravidlo, hypotéza): šestnáctiny přes poslední dvě doby
    var o = start + (bars - 1) * 4;
    notes = notes.filter(function (n) { return n.start_time < o + 2; });
    for (var f = 0; f < 8; f++) notes.push({ pitch: DRUM_PITCH.snare, start_time: o + 2 + f * 0.25, duration: 0.25, velocity: 70 + f * 8 });
  }
  return notes;
}

// ---------- fráze z packů (bass, reese, sub, lead) ----------

var LETTERS = "ABCDEFGH";

function snapToScale(pitch, scale) {
  // nejbližší tón stupnice, při shodě dolů (b6 → 5 by v moll nenastalo, ale v jiné stupnici ano)
  for (var d = 0; d <= 6; d++) {
    if (inScale((pitch - d + 120) % 12, scale)) return pitch - d;
    if (inScale((pitch + d) % 12, scale)) return pitch + d;
  }
  return pitch;
}

function stepInScale(pitch, scale, dir) {
  var p = pitch + dir;
  while (!inScale((p + 120) % 12, scale)) p += dir;
  return p;
}

function pickPhrase(r, bank, m, density) {
  var target = targetDensity(m, density) * 4; // nástupů na 4 takty
  var w = bank.map(function (ph) { return Math.exp(-Math.abs(ph.length - target) / Math.max(2, target * 0.35)); });
  return pickWeighted(r, bank, w);
}

function phraseNotes(role, p, scale, start, bars, plan, busy) {
  // plan = společná harmonie (null = volně), busy = intervaly, kde hraje basa (lead tam mlčí)
  // Skutečná čtyřtaktová fráze z packu: rytmus, výšky a délky drží pohromadě, takty se opakují podle formy z dat.
  // Variace: 0 = doslovně, víc = forma z dat (ABAC, ABCDABCE…), drobné změny tónů a jiný konec čtyřtaktí.
  var m = MODEL.roles[role];
  var bank = MODEL.phrases[role];
  var r = rng(p.seed * 31 + SALT[role] * 7919);
  var ph = pickPhrase(r, bank, m, p.density);
  var src = [[], [], [], []]; // noty po taktech fráze
  ph.forEach(function (n) { src[Math.min(3, Math.floor(n[0] / 16))].push(n); });
  var form = "ABCD";
  var forms = (MODEL.forms && MODEL.forms[role]) || [];
  if (forms.length && r() < 0.3 + 0.7 * p.variation) {
    form = pickWeighted(r, forms.map(function (f) { return f[0]; }), forms.map(function (f) { return f[1]; }));
  }
  var tonic = BASE[role] + scale.root + p.octave * 12;
  // rozsah: nejnižší použitý tón do oktávy nad tóniku, vzdálené tóny o oktávu dolů
  // (vrchní hlas z akordových leadů dělá jinak skoky přes dvě oktávy)
  var used = [];
  for (var ub = 0; ub < Math.min(bars, form.length); ub++) {
    var ul = LETTERS.indexOf(form.charAt(ub));
    src[ul >= 4 ? ub % 4 : ul].forEach(function (n) { used.push(n[2]); });
  }
  var shift = used.length ? 12 * Math.floor(Math.min.apply(null, used) / 12) : 0;
  var span = role === "lead" ? 16 : 24; // basové fráze nechat celé, přeložení by rozbilo kontur motivu
  function fold(rel) {
    rel -= shift;
    while (rel > span) rel -= 12;
    return rel;
  }
  var events = [];
  var varied = {}; // písmeno -> už pozměněný takt (stejné písmeno = stejný takt i po změně)
  for (var b = 0; b < bars; b++) {
    var letter = form.charAt(b % form.length);
    var li = LETTERS.indexOf(letter);
    // E, F… (např. ABCDABCE) = varianta taktu na stejné pozici ve čtyřtaktí
    var bar = src[li >= 4 ? b % 4 : li].map(function (n) { return [n[0] % 16, n[1], n[2]]; });
    if (li >= 4 || (letter !== "A" && !varied[letter] && r() < p.variation * 0.4)) {
      // nové písmeno za D (E, F…) nebo náhodná variace: jeden tón o stupeň vedle, rytmus zůstává
      if (bar.length) {
        var k = Math.floor(r() * bar.length);
        bar[k] = [bar[k][0], bar[k][1], bar[k][2] + (r() < 0.5 ? -1 : 1) * (r() < 0.5 ? 1 : 2)];
      }
    }
    if (varied[letter]) bar = varied[letter];
    else varied[letter] = bar;
    var ending = b % 4 === 3 && b === bars - 1 && p.variation >= 0.4 && bar.length >= 2;
    for (var j = 0; j < bar.length; j++) {
      var n = bar[j];
      var rel = fold(n[2]);
      if (ending && j === bar.length - 1) rel = [0, 7, 12, -2][Math.floor(r() * 4)]; // konec fráze: zpátky k tónice/kvintě
      var t = b * 4 + n[0] * 0.25;
      if (busy && busy.some(function (iv) { return t >= iv[0] && t < iv[1]; })) continue; // odpověď: basa hraje
      var pitch;
      if (role === "sub") {
        var pc = ((rel % 12) + 12) % 12;
        pitch = tonic + pc - (pc > 7 ? 12 : 0); // sub v jedné oktávě kolem tóniky, b6/b7 pod ní
      } else {
        pitch = tonic + rel;
      }
      if (plan) {
        pitch = followChord(pitch, rel, n[0], n[1], plan.at(t), scale, role);
        if (role === "sub") { while (pitch > tonic + 7) pitch -= 12; while (pitch < tonic - 5) pitch += 12; }
      }
      if (!inScale((pitch + 120) % 12, scale)) {
        var keep = role === "reese" && r() < p.variation; // reese smí chromaticky (Ekwols)
        if (!keep) pitch = snapToScale(pitch, scale);
      }
      events.push({ t: t, gap: 0, vel: velocity(r, m, n[0]), dur0: n[1] * 0.25,
                    pitches: voice(scale, pitch, role === "sub" ? "Mono" : voicingFor(role, p.voicing), BASE[role] <= 36) });
    }
  }
  events.sort(function (a, b2) { return a.t - b2.t; });
  for (var e = 0; e < events.length; e++) events[e].gap = (e + 1 < events.length ? events[e + 1].t : bars * 4) - events[e].t;
  var notes = [];
  events.forEach(function (ev, i) {
    var dur = legatoDur(role, ev, events[i + 1], p.legato);
    ev.pitches.forEach(function (pt) {
      if (pt >= 0 && pt <= 127) notes.push({ pitch: pt, start_time: start + ev.t, duration: dur, velocity: ev.vel });
    });
  });
  return notes;
}

// ---------- progrese z packů (Pad) ----------

function padNotes(p, scale, start, bars, plan) {
  // Skutečná čtyřtaktová progrese s původním voicingem (basový tón + akord otevřeně nad ním).
  // Hustota: nízko držené akordy, vysoko rytmické stabsy. Variace: druhý čtyřtakt jiná progrese se stejným začátkem.
  var bank = MODEL.progressions;
  var r = rng(p.seed * 31 + SALT.harmony * 7919);
  var targetDur = 8 * Math.pow(2, -p.density * 4); // doby na akord: 8 → 0,5
  function pick(filterRoot) {
    var cands = filterRoot === undefined ? bank : bank.filter(function (pr) { return pr[0][2] === filterRoot; });
    if (!cands.length) cands = bank;
    var w = cands.map(function (pr) {
      var avg = pr.reduce(function (s, c) { return s + c[1]; }, 0) / pr.length / 4;
      // progrese s kořeny mimo stupnici klipu (bII ve frygické, V v harmonické) jen když stupnice sedí
      var fits = pr.every(function (c) { return inScale((scale.root + c[2]) % 12, scale); });
      return Math.exp(-Math.abs(Math.log(avg / targetDur) / Math.LN2)) * (fits ? 1 : 0.03);
    });
    return pickWeighted(r, cands, w);
  }
  var first = plan ? plan.prog : pick();
  var mode = voicingFor("harmony", p.voicing);
  var notes = [];
  for (var blk = 0; blk * 4 < bars; blk++) {
    var prog = !plan && blk % 2 === 1 && r() < p.variation ? pick(first[0][2]) : first;
    if (plan) prog = rhythmize(r, prog, p.density); // harmonie pevná, Hustota mění jen rytmus akordů
    prog.forEach(function (c) {
      var t = blk * 16 + c[0] * 0.25;
      if (t >= bars * 4) return;
      var bassPitch = 36 + ((scale.root + c[2]) % 12) + p.octave * 12; // basový tón akordu v oktávě C1
      var vo = c[3].slice(0, 6);
      var pitches;
      if (mode === "Mono") pitches = [bassPitch];
      else if (mode === "Kvinta") pitches = [bassPitch, bassPitch + 7, bassPitch + 12];
      else if (mode === "Oktáva") pitches = [bassPitch, bassPitch + 12];
      else if (mode === "Akord") pitches = vo.slice(0, 4).map(function (x) { return bassPitch + x; });
      else pitches = vo.map(function (x) { return bassPitch + x; }); // Auto / Akord 9 = celý voicing z dat
      var seen = {};
      pitches.forEach(function (pt) {
        pt = snapToScale(pt, scale); // tóny akordu do stupnice klipu (durová tercie na v → mollová atd.)
        if (pt <= 127 && !seen[pt]) {
          seen[pt] = true;
          notes.push({ pitch: pt, start_time: start + t, duration: c[1] * 0.25, velocity: 90 });
        }
      });
    });
  }
  return notes;
}

// ---------- společná harmonie (Vazba) ----------

var LINKS = ["Volně", "Harm", "Odpověď"];
var PLAN_SALT = 11;

function harmonyPlan(p, scale) {
  // Progrese jen ze seedu a tóniny klipu (ne z role ani knobů): tracky se stejným seedem mají stejnou harmonii.
  var bank = MODEL.progressions;
  var r = rng(p.seed * 31 + PLAN_SALT * 7919);
  var w = bank.map(function (pr) {
    var fits = pr.every(function (c) { return inScale((scale.root + c[2]) % 12, scale); });
    return (fits ? 1 : 0.03) * (pr[0][2] === 0 ? 2 : 1); // začátek na tónice o něco častěji
  });
  var prog = pickWeighted(r, bank, w);
  var chords = prog.map(function (c) {
    var bassPc = snapToScale(scale.root + c[2], scale) % 12;
    var pcs = {};
    // jádro akordu = první 4 tóny voicingu (to hraje Pad v Auto); vyšší barvy (maj7, 9) basu nepřitahují
    c[3].slice(0, 4).forEach(function (v) { pcs[snapToScale(bassPc + 24 + v, scale) % 12] = true; });
    pcs[bassPc] = true;
    return { t: c[0] * 0.25, root: ((bassPc - scale.root) % 12 + 12) % 12, pcs: pcs };
  });
  return {
    prog: prog,
    at: function (t) {
      // akord platný v čase t (smyčka 4 takty); před prvním akordem platí poslední (předtaktí)
      var tt = ((t % 16) + 16) % 16, cur = chords[chords.length - 1];
      for (var i = 0; i < chords.length; i++) if (chords[i].t <= tt + 1e-6) cur = chords[i];
      return cur;
    },
  };
}

function nearestPc(pitch, okPc, preferDown) {
  for (var d = 0; d <= 6; d++) {
    var a = preferDown ? pitch - d : pitch + d, b = preferDown ? pitch + d : pitch - d;
    if (okPc(((a % 12) + 12) % 12)) return a;
    if (okPc(((b % 12) + 12) % 12)) return b;
  }
  return pitch;
}

function followChord(pitch, rel, slot, dur16, ch, scale, role) {
  // tónika fráze -> kořen akordu; dlouhé tóny a tóny na době -> tón akordu; krátké průchody zůstávají
  var rootPc = (scale.root + ch.root) % 12;
  var low = BASE[role] <= 36;
  if ((((rel % 12) + 12) % 12) === 0) return nearestPc(pitch, function (pc) { return pc === rootPc; }, low);
  if ((slot % 4 === 0 || dur16 >= 2) && !ch.pcs[((pitch % 12) + 12) % 12]) {
    return nearestPc(pitch, function (pc) { return !!ch.pcs[pc]; }, low);
  }
  return pitch;
}

function busyFromNotes(notes) {
  // útok basy (půl doby od nástupu): tam lead mlčí, odpovídá do mezer mezi údery basy
  var seen = {}, out = [];
  notes.forEach(function (n) {
    if (seen[n.start_time]) return;
    seen[n.start_time] = true;
    out.push([n.start_time - 0.01, n.start_time + Math.min(n.duration, 0.5)]);
  });
  return out;
}

function rhythmize(r, prog, density) {
  // stejné akordy, jiný rytmus: nízko držet až do další změny, uprostřed jak v datech, vysoko stabsy z banky Padu
  if (density < 0.34) {
    return prog.map(function (c, i) {
      var nxt = i + 1 < prog.length ? prog[i + 1][0] : 64;
      return [c[0], Math.max(c[1], nxt - c[0]), c[2], c[3]];
    });
  }
  var bank = MODEL.roles.harmony && MODEL.roles.harmony.rhythms2;
  if (density < 0.67 || !bank || !bank.length) return prog;
  var rh = pickRhythm(r, MODEL.roles.harmony, 0.8, bank, 2, 0.5);
  var onsets = [];
  for (var u = 0; u < 2; u++) for (var i = 0; i < 32; i++) if (rh.charAt(i) === "x") onsets.push(u * 32 + i);
  var at = function (sl) { var cur = prog[prog.length - 1]; prog.forEach(function (c) { if (c[0] <= sl) cur = c; }); return cur; };
  prog.forEach(function (c) { if (onsets.indexOf(c[0]) < 0) onsets.push(c[0]); }); // změny akordu vždy zazní
  onsets.sort(function (a, b) { return a - b; });
  return onsets.map(function (sl, i) {
    var c = at(sl), nxt = i + 1 < onsets.length ? onsets[i + 1] : 64;
    return [sl, Math.max(1, Math.min(nxt - sl, 4)), c[2], c[3]];
  });
}

function hasPhrases(role) {
  return MODEL.phrases && MODEL.phrases[role] && MODEL.phrases[role].length >= 8;
}

function generate(params, context) {
  var p = params;
  var scale = DEFAULT_SCALE;
  if (context && context.scale && context.scale.scale_intervals && context.scale.scale_intervals.length) {
    scale = { root: context.scale.root_note % 12, intervals: context.scale.scale_intervals.slice() };
  }
  var start = 0, bars = BAR_CHOICES[p.barsIndex] || 4;
  var sel = context && context.time_selection;
  var end = null;
  if (sel && sel.end_time > sel.start_time) {
    start = sel.start_time;
    if (!BAR_CHOICES[p.barsIndex]) {
      // celé takty přes výběr, noty za koncem výběru se pak odříznou
      bars = Math.max(1, Math.min(32, Math.ceil((sel.end_time - sel.start_time) / 4 - 1e-6)));
      end = sel.end_time;
    }
  } else if (context && typeof context.insert_marker_time === "number") {
    start = context.insert_marker_time; // bez výběru od insert markeru, jako nativní generátory
  }
  var role = ROLES[p.role];
  var parts = role === "drums" ? ["kick", "snare", "hats"] : [role];
  var hasProgs = MODEL.progressions && MODEL.progressions.length;
  var plan = p.link >= 1 && hasProgs ? harmonyPlan(p, scale) : null;
  var busy = null;
  if (role === "lead" && p.link === 2 && hasPhrases("bass")) {
    // odpověď: basa se stejným seedem a knoby (spočítaná tady, MIDI Tool jiné tracky nevidí)
    var bp = {}; for (var key in p) bp[key] = p[key];
    bp.octave = 0; bp.voicing = 0; bp.legato = 0.5;
    busy = busyFromNotes(phraseNotes("bass", bp, scale, 0, bars, plan, null));
  }
  var lp = p;
  if (busy) { lp = {}; for (var k2 in p) lp[k2] = p[k2]; lp.density = Math.min(1, p.density + 0.3); } // hustší fráze, ať je čím odpovídat
  var notes = [];
  parts.forEach(function (x) {
    var made = x === "harmony" && hasProgs ? padNotes(p, scale, start, bars, plan)
      : hasPhrases(x) ? phraseNotes(x, x === "lead" ? lp : p, scale, start, bars, plan, x === "lead" ? busy : null)
      : genRole(x, p, scale, start, bars, plan); // bicí, stab a role bez frází: rytmická banka
    notes = notes.concat(made);
  });
  if (end !== null) {
    notes = notes.filter(function (n) { return n.start_time < end - 1e-6; });
    notes.forEach(function (n) { n.duration = Math.min(n.duration, end - n.start_time); });
  }
  return notes.map(function (n) {
    return { pitch: n.pitch, start_time: n.start_time, duration: n.duration, velocity: n.velocity,
             mute: 0, probability: 1, velocity_deviation: 0, release_velocity: 64 };
  });
}

// ---------- Max ----------

var params = { role: 1, barsIndex: 0, density: 0.5, variation: 0.3, seed: 1, octave: 0, legato: 0.5, voicing: 0, link: 1 };
var context = null;

if (typeof outlet === "function") {
  inlets = 2;
  outlets = 2;
}

function role(v) { params.role = Math.max(0, Math.min(ROLES.length - 1, v | 0)); }
function bars(v) { params.barsIndex = Math.max(0, Math.min(BAR_CHOICES.length - 1, v | 0)); }
function density(v) { params.density = Math.max(0, Math.min(1, v / 100)); }
function variation(v) { params.variation = Math.max(0, Math.min(1, v / 100)); }
function seed(v) { params.seed = Math.max(1, v | 0); }
function octave(v) { params.octave = Math.max(-2, Math.min(2, v | 0)); }
function legato(v) { params.legato = Math.max(0, Math.min(1, v / 100)); }
function voicing(v) { params.voicing = Math.max(0, Math.min(VOICINGS.length - 1, v | 0)); }
function link(v) { params.link = Math.max(0, Math.min(LINKS.length - 1, v | 0)); }
function dice() {
  params.seed = 1 + Math.floor(Math.random() * 999);
  outlet(1, params.seed); // do live.numbox: uloží se se setem a jeho výstup spustí nové generování
}

var got = [false, false]; // [noty klipu, kontext] v tomhle kole

function dictionary(name) {
  // live.miditool.in pošle noty i kontext; pořadí není zaručené, takže generuj až po obou
  var d = new Dict(name);
  if (inlet === 1) {
    context = JSON.parse(d.stringify());
    if (typeof post === "function") // Max konzole: co Live poslal (výběr, marker), pro ladění
      post("NPOS kontext: výběr " + JSON.stringify(context.time_selection || null) + ", marker " + context.insert_marker_time + "\n");
  }
  got[inlet === 1 ? 1 : 0] = true;
  if (!(got[0] && got[1])) return;
  got = [false, false];
  var out = new Dict();
  out.parse(JSON.stringify({ notes: generate(params, context) }));
  outlet(0, "dictionary", out.name);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { generate: generate, setModel: function (m) { MODEL = m; }, ROLES: ROLES, ROLE_LABELS: ROLE_LABELS, VOICINGS: VOICINGS, LINKS: LINKS, BAR_CHOICES: BAR_CHOICES };
}
