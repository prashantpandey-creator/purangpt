# Secrets management (SOPS + age)

All PuranGPT dev/ops secrets live **encrypted** in `secrets/prod.enc.yaml`,
committed to git. Only holders of an age private key listed in `../.sops.yaml`
can decrypt. Plaintext never gets committed (`.gitignore` blocks everything under
`secrets/` except `*.enc.yaml`).

## One-time setup on a new machine / session
1. Install tools: `brew install sops age` (macOS) or your package manager.
2. Get the age **private** key (out-of-band — NOT via git) and place it at
   `~/.config/sops/age/keys.txt` (`chmod 600`).
3. Done — `sops` auto-finds the key there.

## Daily use
```bash
sops secrets/prod.enc.yaml            # open decrypted in $EDITOR, re-encrypts on save
sops -d secrets/prod.enc.yaml         # print decrypted to stdout
sops -d --extract '["backend"]["VECTOR_DB_URL"]' secrets/prod.enc.yaml   # one value
```

## Structure
```yaml
backend:    # → becomes /root/purangpt/.env on the server
  LLM_PROVIDER: ...
  VECTOR_DB_URL: ...
  ...
frontend:   # → becomes /root/frontend-secrets.env on the server
  LOGTO_APP_SECRET: ...
  ...
```

## Push secrets to the server
After editing, regenerate the server env files from the encrypted source:
```bash
./secrets/sync-to-server.sh        # decrypts locally, writes the two .env files on the box
```
This decrypts in memory, scp's the rendered `.env` files to the server, and never
writes plaintext to disk locally.

## Granting access to another machine/session
1. On the new machine: `age-keygen -o ~/.config/sops/age/keys.txt`, copy its
   `# public key:` line.
2. Add that public key under `key_groups.age` in `../.sops.yaml`.
3. Re-encrypt for the new recipient: `sops updatekeys secrets/prod.enc.yaml`.
4. Commit `.sops.yaml` + the re-keyed `secrets/prod.enc.yaml`.

## Rotating a secret
Edit the value via `sops secrets/prod.enc.yaml`, then `./secrets/sync-to-server.sh`
and redeploy (or restart) the affected service.
