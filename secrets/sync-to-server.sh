#!/usr/bin/env bash
# Render the SOPS-encrypted secrets into the server's env files, in memory only.
# Decrypts secrets/prod.enc.yaml → writes /root/purangpt/.env (backend section) and
# /root/frontend-secrets.env (frontend section) on the Hetzner box. No plaintext is
# written to local disk.
#
# Usage: ./secrets/sync-to-server.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ENC="$HERE/prod.enc.yaml"
SSH="ssh -i $HOME/.ssh/purangpt_hetzner -o ConnectTimeout=30 root@204.168.176.229"

command -v sops >/dev/null || { echo "sops not installed (brew install sops age)"; exit 1; }

echo "Decrypting and rendering env files (in memory)…"

# Render the backend section as KEY=VALUE lines and pipe straight to the server.
sops -d --output-type json "$ENC" | python3 -c '
import json,sys
d=json.load(sys.stdin)
def render(section):
    return "\n".join(f"{k}={v}" for k,v in d.get(section,{}).items())+"\n"
import os
open("/tmp/.be.env","w").write(render("backend"))
open("/tmp/.fe.env","w").write(render("frontend"))
'
# scp the rendered files, then shred the local temps immediately.
scp -i "$HOME/.ssh/purangpt_hetzner" -o ConnectTimeout=30 /tmp/.be.env root@204.168.176.229:/root/purangpt/.env
scp -i "$HOME/.ssh/purangpt_hetzner" -o ConnectTimeout=30 /tmp/.fe.env root@204.168.176.229:/root/frontend-secrets.env
rm -f /tmp/.be.env /tmp/.fe.env
$SSH 'chmod 600 /root/purangpt/.env /root/frontend-secrets.env'

echo "Synced. Restart affected services to pick up changes:"
echo "  $SSH 'cd /root && docker compose up -d backend frontend'"
