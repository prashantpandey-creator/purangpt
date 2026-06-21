#!/bin/sh
# Xcode Cloud post-clone — installs node_modules so SPM local-path packages resolve.
set -e

echo "=== ci_post_clone: node setup ==="

# Xcode Cloud runners ship with nvm; activate it.
export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Use Node 20 LTS if available, otherwise fall back to whatever is on PATH.
if command -v nvm >/dev/null 2>&1; then
  nvm install 20 --no-progress
  nvm use 20
elif command -v brew >/dev/null 2>&1 && ! command -v node >/dev/null 2>&1; then
  brew install node@20
  export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
fi

node --version
npm --version

echo "=== ci_post_clone: npm install ==="
cd "$CI_PRIMARY_REPOSITORY_PATH"
npm ci || npm install

echo "=== ci_post_clone: cap sync ios ==="
npx cap sync ios --no-build

echo "=== ci_post_clone: done ==="
