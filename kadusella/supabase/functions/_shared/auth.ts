import { verifyToken } from "npm:@clerk/backend@3.2.2";

/**
 * Verifies Clerk session JWT from Authorization: Bearer <token>.
 * Set CLERK_SECRET_KEY in Edge Function secrets.
 */
export async function requireClerkUserId(req: Request): Promise<string> {
  const header = req.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) {
    throw new Error("Missing bearer token");
  }
  const token = header.slice("Bearer ".length).trim();
  const secretKey = Deno.env.get("CLERK_SECRET_KEY");
  if (!secretKey) {
    throw new Error("CLERK_SECRET_KEY not configured");
  }
  const payload = await verifyToken(token, { secretKey });
  const sub = payload.sub;
  if (!sub) throw new Error("Invalid token: no sub");
  return sub;
}

/** Optional shared secret for server-to-server calls from Next.js (bypasses Clerk JWT). */
export function assertInternalSecret(req: Request): void {
  const expected = Deno.env.get("EDGE_INTERNAL_SECRET");
  if (!expected) return;
  const got = req.headers.get("x-internal-secret");
  if (got !== expected) {
    throw new Error("Invalid internal secret");
  }
}
