# PuranGPT — Deployment Architecture (canonical)

> Single source of truth for how PuranGPT deploys. If you find a second mechanism
> doing the same job, it's drift — reconcile it to this doc.

## TL;DR

- **Two repos, one deploy path each, both via GitHub Actions on `main`.**
  - Backend  → `prashantpandey-creator/purangpt`      → `.github/workflows/deploy.yml`
  - Frontend → `frontend/` in this monorepo → `.github/workflows/deploy.yml`
- **`main` is the only deploy branch.** `develop` is dead — never deploy from it.
- The **production stack compose is version-controlled** at
  `deploy/docker-compose.prod.yml` (the sanitized mirror of the server's
  `/root/docker-compose.yml`). It owns: backend, frontend, logto, logto-db. The
  pgvector DB (`purangpt-pgvector-1`) is a SEPARATE compose project (`purangpt`)
  reached via the external `purangpt_default` network. Secrets are NOT inline —
  they come from gitignored env files (`/root/stack.env`, `/root/purangpt-monorepo/.env`,
  `/root/frontend-secrets.env`); template in `deploy/.env.prod.example`.
  > Server cutover (pending): replace `/root/docker-compose.yml` with this file +
  > create `/root/stack.env` from the template, so the live file matches git.
- **Coolify** runs on this box but only provides the **Traefik proxy + SSL**. It does
  NOT build or deploy PuranGPT — no Coolify "application" is defined for it. Don't
  expect Coolify Git integration to do anything here.

## The one deploy flow

```
git push origin main
  → GitHub Actions (deploy.yml)
      → SSH to Hetzner (204.168.176.229); key = repo secret VPS_SSH_KEY
      → cd /root/<repo>; git fetch origin main; git reset --hard origin/main; git clean -fd
      → cd /root; docker compose build [--no-cache for frontend] <service>
      → docker compose up -d <service>
```

Rules:
- **Never `git pull` on the server** — it aborts on a dirty tree and silently ships
  stale code. Always fetch + `reset --hard origin/main` + `clean -fd`.
- Backend skips `--no-cache` (heavy pip/sentence-transformers layers stay cached).
  Frontend forces `--no-cache` (the standalone build caches `npm run build` wrongly).
- A real frontend build is ~1–4 min. A sub-minute "success" is a cache/abort, not a
  deploy — verify by curling the live route/asset.

## Why it's set up this way (traps that were removed)

This stack had accreted **three** overlapping deploy mechanisms fighting each other:

1. **GitHub Actions** — KEPT, the canonical one. Hard-reset, path-filtered, no-cache
   frontend. Reproducible, rollback-able.
2. **`webhook.py` on :9000** — REMOVED from the deploy path. It ran `/root/deploy-*.sh`
   which did `git pull origin develop` for the backend: `git pull` aborts on a dirty
   tree, and `develop` was the wrong (stale) branch — so backend changes silently
   never shipped. This was the original "my changes aren't deploying" bug.
3. **An in-repo `docker-compose.yml`** that also defined `pgvector`/`ollama` with
   `POSTGRES_PASSWORD=postgres` + `ports: 5432:5432`. Running it desynced the DB
   password (broke live auth) and **published Postgres to the internet** (→ breach).
   The in-repo compose is now LOCAL-DEV-ONLY: no pgvector service, no port publish.

## Server facts

- Backend dir: `/root/purangpt`        (must be on `main`)
- Frontend dir: `/root/purangpt-monorepo/frontend`  (on `main`)
- Root compose: `/root/docker-compose.yml`  ← production source of truth
- Frontend server-side secrets: `/root/frontend-secrets.env` (gitignored, injected
  via the frontend service `env_file:` — see `purangpt-next/CLAUDE-secrets.md`).
- pgvector port 5432 is firewalled to Docker-internal only (DOCKER-USER iptables).

## Security invariants (learned the hard way)

- **No DB port (5432/6379/27017) may be published to `0.0.0.0`.** Docker bypasses
  ufw — publishing a port exposes it to the internet regardless of the firewall.
- **No secrets in source or in committed compose `environment:` blocks** — use
  `env_file:` pointing at a gitignored file.
- `FERNET_KEY`, `LOGTO_*`, `GOOGLE_*` must be real env vars; the apps fail fast if
  missing rather than falling back to a leaked hardcoded default.

---

## Appendix — iOS App (Capacitor)

Capacitor wraps the web frontend into a native iOS app (no rewrite). Lives in
`purangpt-next` (the Capacitor config + `@logto/capacitor`), not the backend.

```bash
cd frontend
npx cap sync ios     # copy web build into the iOS bundle after each change
npx cap open ios     # open Xcode → select device → Run
```

App Store metadata:
- **Name:** PuranGPT · **Subtitle:** AI Oracle of the Sacred Texts
- **Bundle ID:** `com.purangpt.app` · **Category:** Books / Education
- **Description:** Explore the 18 Mahapuranas, Vedas, Upanishads, and Yogic
  scriptures through AI conversation. Every answer includes exact verse citations
  in Sanskrit and English.
