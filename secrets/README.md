# secrets/ — SOPS-encrypted secrets

Production secrets for the PuranGPT backend, encrypted with
[SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age).
Only the **values** are encrypted; keys stay in cleartext so diffs are reviewable.
Encryption recipients are declared in [`../.sops.yaml`](../.sops.yaml).

| File | Purpose |
|------|---------|
| `prod.env` | Production secret values (dotenv). Decrypts to `.env` at the repo root. |

## Prerequisites

```bash
# sops + age binaries
age --version && sops --version
```

## Decryption key

Decryption needs the **age private key** matching the recipient in `.sops.yaml`
(`age180875puaf7lkxye3pfdwq2u0ww9hq0hjc3xmwc53q8eudzxnxfdsnzjh8e`). Point sops at
it with **one** of:

```bash
export SOPS_AGE_KEY_FILE=/path/to/keys.txt      # file containing AGE-SECRET-KEY-...
# or
export SOPS_AGE_KEY="AGE-SECRET-KEY-1........."  # the key material directly
```

The private key is **never** committed. Keep it in your password manager / the
deploy host / CI secret store.

## Everyday use

```bash
# Edit secrets (opens decrypted in $EDITOR, re-encrypts on save)
sops secrets/prod.env

# Render to a usable .env (git-ignored) for local run / deploy
sops -d secrets/prod.env > .env

# Rotate / add a recipient: add their age pubkey to BOTH rules in .sops.yaml, then
sops updatekeys secrets/prod.env
```

> First-commit values are `REPLACE_ME` placeholders. Run `sops secrets/prod.env`
> and fill in the real secrets before deploying.

## Deploy integration (wired in `.github/workflows/deploy.yml`)

On every deploy the workflow SSHes to Hetzner and — after `git reset --hard` +
`git clean -fd` — installs `sops` (if missing) and renders the secrets:

```bash
SOPS_AGE_KEY="$SOPS_AGE_KEY" sops -d secrets/prod.env > /root/purangpt/.env   # chmod 600
```

It aborts the deploy if the rendered `.env` still contains `REPLACE_ME`, so
placeholder secrets can never reach production.

**Two one-time setup steps required:**

1. Add the age **private** key as a repo Actions secret named `SOPS_AGE_KEY`
   (value: `AGE-SECRET-KEY-1…`).
2. Make the production compose at `/root/docker-compose.yml` feed this file to the
   backend service:

   ```yaml
   services:
     backend:
       env_file:
         - ./purangpt/.env
   ```

> The workflow deliberately writes to **`/root/purangpt/.env`**, not `/root/.env`,
> to avoid clobbering the combined host env used by the logto/frontend services.
> `.env` is git-ignored, so the decrypted file never re-enters version control.
