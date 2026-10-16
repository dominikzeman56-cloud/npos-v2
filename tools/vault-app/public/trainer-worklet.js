// AudioWorklet: obálka kolem Engine z trainer-dsp.js. Výstupy: 0 = zvuk, 1 = modulace cutoffu, 2 = modulace driveu.
import { Engine } from './trainer-dsp.js';

class TrainerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.engine = new Engine(sampleRate, []);
    this.cut = new Float32Array(128);
    this.drv = new Float32Array(128);
    this.port.onmessage = (e) => {
      const m = e.data;
      if (m.type === 'table') this.engine.tables[m.index] = m.table;
      else if (m.type === 'set') this.engine.set(m.params);
      else if (m.type === 'on') this.engine.noteOn(m.freq);
      else if (m.type === 'off') this.engine.noteOff();
      else if (m.type === 'freq') this.engine.freq = m.freq;
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0], cut = outputs[1][0], drv = outputs[2][0];
    const n = out.length;
    this.engine.process(out, cut, drv, n);
    if (outputs[0].length > 1) outputs[0][1].set(out);
    return true;
  }
}
registerProcessor('trainer', TrainerProcessor);
