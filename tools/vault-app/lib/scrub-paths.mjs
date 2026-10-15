// Hides local absolute Windows paths (D:\…, C:\Users\…) in the shared export; keeps only the last segment.
// The vault originals stay untouched — this runs on the payload only.
const LOCAL = '‹lokálně›/';
const DRIVE = /^[A-Za-z]:[\\/]/;

const base = (p) => {
  const segs = p.split(/[\\/]+/).filter(Boolean);
  return segs.length > 1 ? LOCAL + segs[segs.length - 1] : LOCAL;
};

export function scrubPaths(s) {
  if (typeof s !== 'string' || !/[A-Za-z]:[\\/]/.test(s)) return s;
  if (DRIVE.test(s) && !s.includes('\n')) return base(s.trim()); // whole value is a path (frontmatter)
  return s
    .replace(/`([A-Za-z]:[\\/][^`\n]*)`/g, (_, p) => '`' + base(p) + '`')
    .replace(/"([A-Za-z]:[\\/][^"\n]*)"/g, (_, p) => '"' + base(p) + '"')
    .replace(/(^|[^\w`"])([A-Za-z]:[\\/][^\s`"'|)<>*]*)/g, (_, pre, p) => pre + base(p));
}

// Deep-scrub every string in a JSON-able value.
export const scrubDeep = (v) => JSON.parse(JSON.stringify(v, (_, x) => scrubPaths(x)));
