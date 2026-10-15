// Vercel Routing Middleware: shared-password gate (HTTP Basic Auth) in front of EVERYTHING, incl. /data and /files.
// The password lives only in the VAULT_PASSWORD env var of the Vercel project. Fails closed if it is missing.
import { next } from '@vercel/functions';

const enc = new TextEncoder();
const sha = async (s) => new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(s)));
const same = (a, b) => { let d = a.length ^ b.length; for (let i = 0; i < a.length && i < b.length; i++) d |= a[i] ^ b[i]; return d === 0; };

const deny = (status, msg) =>
  new Response(msg, {
    status,
    headers: { 'WWW-Authenticate': 'Basic realm="Vault", charset="UTF-8"', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow' },
  });

export default async function middleware(request) {
  const pass = process.env.VAULT_PASSWORD;
  if (!pass) return new Response('Server is not configured (VAULT_PASSWORD missing).', { status: 500, headers: { 'Cache-Control': 'no-store' } });

  const h = request.headers.get('authorization') || '';
  if (h.startsWith('Basic ')) {
    try {
      const bytes = Uint8Array.from(atob(h.slice(6).trim()), (c) => c.charCodeAt(0));
      const decoded = new TextDecoder().decode(bytes);
      const given = decoded.slice(decoded.indexOf(':') + 1); // username is ignored
      if (same(await sha(given), await sha(pass))) {
        return next({ headers: { 'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex, nofollow' } });
      }
    } catch { /* malformed header → fall through to 401 */ }
  }
  return deny(401, 'Přihlášení vyžadováno.');
}
