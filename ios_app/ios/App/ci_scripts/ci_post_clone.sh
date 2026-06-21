#!/bin/sh
# Xcode Cloud post-clone — installs Capacitor deps so SPM local-path packages resolve.
set -e

echo "=== ci_post_clone: node setup ==="

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

if command -v nvm >/dev/null 2>&1; then
  nvm install 20 --no-progress
  nvm use 20
fi

node --version
npm --version

echo "=== ci_post_clone: npm install (ios_app) ==="
cd "$CI_PRIMARY_REPOSITORY_PATH/ios_app"
npm install

echo "=== ci_post_clone: cap sync ios ==="
npx cap sync ios --no-build

echo "=== ci_post_clone: done ==="
