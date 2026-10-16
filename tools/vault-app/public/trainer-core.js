// Trenažér syntézy: čistá matematika bez Web Audio (jde ji testovat v Node). Žádná data presetů, žádný obsah cizích packů:
// wavetable se generují aditivně z jednoduchých vzorců.
export const FRAMES = 16;            // snímků v jedné tabulce
export const SIZE = 2048;            // vzorků jednoho cyklu
export const MAXH = [512, 256, 128, 64, 32, 16, 8, 4];   // mip: nejvyšší harmonická, aby tabulka při dané výšce nealiasovala
export const CURVE_RANGE = 16;       // křivka waveshaperu pokrývá vstup ±16 (po pre-gainu), jinak by WaveShaperNode ořízl vstup na ±1

// ── tempo, výška, poměry ─────────────────────────────────────────────────────────────────────────────────────
export const DIVISIONS = [['1/1', 4], ['1/2', 2], ['1/4', 1], ['1/8T', 1 / 1.5], ['1/8', 0.5], ['1/16T', 1 / 3], ['1/16', 0.25], ['1/32', 0.125]];
export const syncRateHz = (bpm, div) => {
  const beats = (DIVISIONS.find((d) => d[0] === div) || [, 1])[1];
  return bpm / 60 / beats;
};
export const midiToHz = (n) => 440 * 2 ** ((n - 69) / 12);
const NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
export const noteName = (n) => NAMES[((n % 12) + 12) % 12] + (Math.floor(n / 12) - 1);
// kolik centů je poměr od nejbližšího násobku půltónu (bin N = N × fundament, ne N půltónů)
export function centsFromEqual(ratio) {
  const c = 1200 * Math.log2(ratio);
  const semis = Math.round(c / 100);
  return { cents: c, semis, dev: c - semis * 100 };
}

// ── wavetable: aditivní snímky ───────────────────────────────────────────────────────────────────────────────
// Snímek = pole amplitud a fází harmonických: x(t) = Σ a_h · sin(2π h t + φ_h)
export const TABLE_KINDS = [
  { id: 'sine', name: 'Sinus', desc: 'Čistý sinus ve všech snímcích; výchozí pro sub. Pozice tabulky nic nemění.' },
  { id: 'saw-square', name: 'Saw → Square', desc: 'Pila (všechny harmonické 1/h) se postupně mění na obdélník (jen liché).' },
  { id: 'additive', name: 'Přibývání harmonických', desc: 'Od sinu po jasnou pilu: každý snímek přidá další harmonické.' },
  { id: 'formant', name: 'Formant (vokál)', desc: 'Pila s tvarovaným hrbem, který putuje vyššími harmonickými: základ „growl“ pohybu pozicí tabulky.' },
  { id: 'third', name: '3. harmonická roste', desc: 'Fundament + sílící 3. harmonická (jak vypadá asymetrické zkreslení, jen jako tvar).' },
  { id: 'pwm', name: 'Pulse width', desc: 'Obdélník s klesající šířkou pulzu (50 % → 5 %).' },
];

export function frameHarmonics(kindIdx, f, maxH) {
  const t = f / (FRAMES - 1);
  const a = new Float32Array(maxH + 1);
  const ph = new Float32Array(maxH + 1);
  const kind = TABLE_KINDS[kindIdx].id;
  for (let h = 1; h <= maxH; h++) {
    if (kind === 'sine') a[h] = h === 1 ? 1 : 0;
    else if (kind === 'saw-square') a[h] = (1 / h) * (h % 2 === 0 ? 1 - t : 1);
    else if (kind === 'additive') a[h] = h <= 1 + t * 40 ? 1 / h : 0;
    else if (kind === 'formant') {
      const c = 2 + t * 20;
      a[h] = (1 / h) * (0.35 + 2.2 * Math.exp(-((h - c) ** 2) / (2 * 2.2 ** 2)));
    } else if (kind === 'third') a[h] = h === 1 ? 1 : h === 3 ? 0.15 + t * 1.65 : h === 2 ? 0.1 : h <= 7 ? 0.05 / h : 0;
    else if (kind === 'pwm') {
      const d = 0.5 - t * 0.45;                 // šířka pulzu
      a[h] = (2 / (Math.PI * h)) * Math.sin(Math.PI * h * d);
      ph[h] = Math.PI / 2;                      // cos fáze: pulz vystředěný na t = 0
    }
  }
  return { a, ph };
}

const SINT = new Float32Array(SIZE), COST = new Float32Array(SIZE);
for (let i = 0; i < SIZE; i++) { SINT[i] = Math.sin((2 * Math.PI * i) / SIZE); COST[i] = Math.cos((2 * Math.PI * i) / SIZE); }

// Vykreslí jednu tabulku: mips[m] = Float32Array(FRAMES · (SIZE + 1)); každý snímek má o vzorek navíc kvůli interpolaci.
export function buildTable(kindIdx) {
  const mips = MAXH.map((mh) => {
    const data = new Float32Array(FRAMES * (SIZE + 1));
    for (let f = 0; f < FRAMES; f++) {
      const { a, ph } = frameHarmonics(kindIdx, f, mh);
      const cs = new Float32Array(mh + 1), ss = new Float32Array(mh + 1);
      for (let h = 1; h <= mh; h++) { cs[h] = a[h] * Math.cos(ph[h]); ss[h] = a[h] * Math.sin(ph[h]); }
      const base = f * (SIZE + 1);
      for (let n = 0; n < SIZE; n++) {
        let x = 0;
        for (let h = 1; h <= mh; h++) {
          if (cs[h] === 0 && ss[h] === 0) continue;
          const idx = (h * n) % SIZE;
          x += cs[h] * SINT[idx] + ss[h] * COST[idx];
        }
        data[base + n] = x;
      }
      data[base + SIZE] = data[base];
    }
    return data;
  });
  // společná normalizace snímku podle mipu 0, aby se hlasitost nemění s výškou tónu ani s pozicí v tabulce
  const peaks = new Float32Array(FRAMES);
  for (let f = 0; f < FRAMES; f++) {
    let pk = 1e-9; const base = f * (SIZE + 1);
    for (let n = 0; n < SIZE; n++) pk = Math.max(pk, Math.abs(mips[0][base + n]));
    peaks[f] = pk;
  }
  for (const data of mips) for (let f = 0; f < FRAMES; f++) { const base = f * (SIZE + 1); for (let n = 0; n <= SIZE; n++) data[base + n] /= peaks[f]; }
  return { frames: FRAMES, size: SIZE, maxH: MAXH, mips };
}

// ── zkreslení ────────────────────────────────────────────────────────────────────────────────────────────────
export const DIST_TYPES = [
  { id: 'soft', name: 'Soft clip (tanh)', desc: 'Symetrický: jen liché harmonické, bez DC.' },
  { id: 'hard', name: 'Hard clip', desc: 'Ostré ořezání: bohaté liché harmonické, tvrdší.' },
  { id: 'fold', name: 'Wavefolder', desc: 'Přetočení vlny zpět: proměnlivé spektrum podle síly signálu.' },
  { id: 'asym', name: 'Asymetrické', desc: 'Liché i sudé harmonické a DC offset. DC je třeba zablokovat.' },
];
export function distCurve(type, n = 16385) {
  const c = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const u = ((i / (n - 1)) * 2 - 1) * CURVE_RANGE;
    let y;
    if (type === 'soft') y = Math.tanh(u);
    else if (type === 'hard') y = Math.max(-1, Math.min(1, u));
    else if (type === 'fold') y = Math.sin((u * Math.PI) / 2);
    else if (type === 'asym') y = Math.tanh(u + 0.6) - Math.tanh(0.6);
    else y = u;
    c[i] = y;
  }
  return c;
}
