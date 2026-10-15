// node --test lib/scrub-paths.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { scrubPaths, scrubDeep } from './scrub-paths.mjs';

test('backticked path with spaces keeps only the last segment', () => {
  assert.equal(scrubPaths('Upload je `D:\\Downloads\\First Contact.mp3` (instr.)'), 'Upload je `‹lokálně›/First Contact.mp3` (instr.)');
});

test('directory path with trailing slash', () => {
  assert.equal(scrubPaths('MIDI: `D:\\Music\\_MIDI_KOSTRY\\HANDS_UP\\`'), 'MIDI: `‹lokálně›/HANDS_UP`');
});

test('whole frontmatter value is a path', () => {
  assert.equal(scrubPaths('C:\\Users\\domin\\Desktop\\Triamer & Nagato - Hands Up.wav'), '‹lokálně›/Triamer & Nagato - Hands Up.wav');
});

test('bare path stops at whitespace, prose survives', () => {
  assert.equal(scrubPaths('| **Systém složek D:\\Ableton** | hotový |'), '| **Systém složek ‹lokálně›/Ableton** | hotový |');
});

test('code-block line', () => {
  assert.equal(scrubPaths('x\nD:\\Music\\Projects\\DIRTS_REMIX\\\ny'), 'x\n‹lokálně›/DIRTS_REMIX\ny');
});

test('non-path text untouched, deep scrub over objects', () => {
  assert.equal(scrubPaths('ratio 4:1, time 1:30'), 'ratio 4:1, time 1:30');
  assert.deepEqual(scrubDeep({ a: ['D:\\x\\y.als'], b: 2 }), { a: ['‹lokálně›/y.als'], b: 2 });
});
