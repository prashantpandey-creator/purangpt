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

## Deploy integration

The Hetzner deploy (`.github/workflows/deploy.yml`) can materialise `.env` on the
server right before `docker compose up` by exposing the age key as a CI/host
secret and running:

```bash
SOPS_AGE_KEY="$AGE_PRIVATE_KEY" sops -d secrets/prod.env > .env
```

`.env` is git-ignored, so the decrypted file never re-enters version control.
