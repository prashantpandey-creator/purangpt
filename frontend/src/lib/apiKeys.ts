/**
 * apiKeys.ts — Pro API key issuance & verification.
 *
 * Keys let a Pro user call the public REST endpoint (`POST /api/v1/chat`)
 * from their own code. We store only a SHA-256 hash of each key — the
 * plaintext is shown exactly once, at creation time, and never again.
 *
 * Table is created lazily (CREATE TABLE IF NOT EXISTS) so the hands-off
 * deploy pipeline needs no separate migration step.
 */
import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { sql } from './db';

const KEY_PREFIX = 'pgk_live_';

export interface ApiKeyRow {
  id: string;
  prefix: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
}

let tableReady: Promise<void> | null = null;

/** Ensure the api_keys table exists (runs once per process). */
function ensureTable(): Promise<void> {
  const db = sql;
  if (!db) return Promise.resolve();
  if (!tableReady) {
    tableReady = db`
      CREATE TABLE IF NOT EXISTS api_keys (
        id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_sub     text NOT NULL,
        key_hash     text NOT NULL UNIQUE,
        prefix       text NOT NULL,
        name         text,
        created_at   timestamptz NOT NULL DEFAULT now(),
        last_used_at timestamptz,
        revoked_at   timestamptz
      )
    `.then(async () => {
      await db`CREATE INDEX IF NOT EXISTS api_keys_user_sub_idx ON api_keys (user_sub)`;
    }).then(() => undefined).catch((err) => {
      // Reset so a later call can retry rather than caching a failed init.
      tableReady = null;
      throw err;
    });
  }
  return tableReady;
}

function hashKey(plaintext: string): string {
  return createHash('sha256').update(plaintext).digest('hex');
}

/**
 * Create a new key for a user. Returns the one-time plaintext alongside the
 * stored row metadata. Caller is responsible for confirming the user is Pro.
 */
export async function createApiKey(
  userSub: string,
  name?: string,
): Promise<{ plaintext: string; row: ApiKeyRow }> {
  if (!sql) throw new Error('Database not configured');
  await ensureTable();

  const plaintext = KEY_PREFIX + randomBytes(24).toString('hex');
  const prefix = plaintext.slice(0, KEY_PREFIX.length + 6); // e.g. pgk_live_a1b2c3
  const key_hash = hashKey(plaintext);

  const result = await sql`
    INSERT INTO api_keys (user_sub, key_hash, prefix, name)
    VALUES (${userSub}, ${key_hash}, ${prefix}, ${name ?? null})
    RETURNING id, prefix, name, created_at, last_used_at
  `;
  return { plaintext, row: result[0] as unknown as ApiKeyRow };
}

/** List a user's active (non-revoked) keys — metadata only, never the key. */
export async function listApiKeys(userSub: string): Promise<ApiKeyRow[]> {
  if (!sql) return [];
  await ensureTable();
  const rows = await sql`
    SELECT id, prefix, name, created_at, last_used_at
    FROM api_keys
    WHERE user_sub = ${userSub} AND revoked_at IS NULL
    ORDER BY created_at DESC
  `;
  return rows as unknown as ApiKeyRow[];
}

/** Revoke one key the user owns. Returns true if a row was revoked. */
export async function revokeApiKey(userSub: string, id: string): Promise<boolean> {
  if (!sql) return false;
  await ensureTable();
  const rows = await sql`
    UPDATE api_keys
    SET revoked_at = now()
    WHERE id = ${id} AND user_sub = ${userSub} AND revoked_at IS NULL
    RETURNING id
  `;
  return rows.length > 0;
}

/**
 * Resolve a presented key to its owner's user_sub, or null if invalid/revoked.
 * Touches last_used_at on success. Uses a constant-time compare on the hash.
 */
export async function resolveApiKey(presented: string | null | undefined): Promise<string | null> {
  if (!sql || !presented || !presented.startsWith(KEY_PREFIX)) return null;
  await ensureTable();

  const key_hash = hashKey(presented.trim());
  const rows = await sql`
    SELECT id, user_sub, key_hash FROM api_keys
    WHERE key_hash = ${key_hash} AND revoked_at IS NULL
    LIMIT 1
  `;
  if (rows.length === 0) return null;

  const row = rows[0] as unknown as { id: string; user_sub: string; key_hash: string };
  // Defensive constant-time check (the WHERE already matched the hash).
  const a = Buffer.from(row.key_hash);
  const b = Buffer.from(key_hash);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  // Best-effort usage timestamp; don't fail the request if this update errors.
  void sql`UPDATE api_keys SET last_used_at = now() WHERE id = ${row.id}`.catch(() => {});
  return row.user_sub;
}
