// Shared App Store Connect API helper. Usage: import { asc, APP_ID } from "./asc.mjs"
import { readFileSync } from "fs";
import { createSign } from "crypto";

const ISSUER = "cd70aca8-fd7b-4e5a-8162-fb3c0c15234b";
const KID = "Y63UQ45MG5";
const KEY = readFileSync(process.env.HOME + "/Downloads/AuthKey_Y63UQ45MG5.p8", "utf8");
export const APP_ID = "6777420142";
export const BASE = "https://api.appstoreconnect.apple.com/v1";

const b64url = (b) =>
  Buffer.from(b).toString("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");

export function token() {
  const now = Math.floor(Date.now() / 1000);
  const h = b64url(JSON.stringify({ alg: "ES256", kid: KID, typ: "JWT" }));
  const p = b64url(JSON.stringify({ iss: ISSUER, iat: now, exp: now + 1200, aud: "appstoreconnect-v1" }));
  const s = createSign("SHA256");
  s.update(h + "." + p);
  return h + "." + p + "." + b64url(s.sign({ key: KEY, dsaEncoding: "ieee-p1363" }));
}

export async function asc(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: { Authorization: "Bearer " + token(), "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* non-json */ }
  return { status: res.status, ok: res.ok, json, text };
}
