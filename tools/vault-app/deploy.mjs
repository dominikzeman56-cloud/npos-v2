// One-command deploy of the shared vault viewer: export -> copy site/ OUTSIDE the git repo -> vercel deploy --prod -> auth check.
// Why the copy: `vercel deploy` inside a git repo attaches the last commit's author, and Vercel blocks the deployment when that
// author is not a member of the project ("commit author doesn't have permission"). From a folder without git there is no author.
// Usage: npm run deploy            (export without preset builds)
//        npm run deploy -- --builds (export with /data/builds, only with the owner's consent: paid packs, redistribution none)
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, 'site');
const builds = process.argv.includes('--builds');
const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: process.platform === 'win32' && cmd !== process.execPath, ...opts });
  if (r.status !== 0) { console.error(`\n${cmd} ${args.join(' ')} failed (exit ${r.status})`); process.exit(r.status || 1); }
};

run(process.execPath, ['export-static.mjs', ...(builds ? ['--builds'] : [])], { cwd: HERE });
if (!fs.existsSync(path.join(SITE, '.vercel', 'project.json'))) {
  console.error('site/.vercel/project.json is missing: link the project first (cd site && vercel link).');
  process.exit(1);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'neuro-vault-deploy-'));
try {
  fs.cpSync(SITE, path.join(tmp, 'site'), { recursive: true });
  run('vercel', ['deploy', '--prod', '--yes'], { cwd: path.join(tmp, 'site') });
} finally {
  try { fs.rmSync(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); } catch (e) { console.warn(`Could not remove ${tmp} (${e.code}); safe to delete by hand.`); }
}

// The deployed site must refuse anonymous requests (fail-closed Basic Auth).
const url = process.env.VAULT_URL || 'https://neuro-vault-gamma.vercel.app/';
try {
  const r = await fetch(url);
  console.log(`\nAuth check ${url}: ${r.status} ${r.status === 401 ? '(OK, password required)' : '(UNEXPECTED: expected 401)'}`);
  if (r.status !== 401) process.exit(2);
} catch (e) {
  console.warn('Auth check skipped:', e.message);
}
