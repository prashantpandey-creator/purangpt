#!/bin/sh
# Xcode Cloud post-clone — resolve Capacitor SPM local-path packages.
#
# Package.swift (ios_app/ios/App/CapApp-SPM/Package.swift) references node_modules
# via ../../../node_modules, which resolves to ios_app/ios/node_modules. npm
# installs to ios_app/node_modules, so we symlink ios_app/ios/node_modules to it.
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

APP_ROOT="$CI_PRIMARY_REPOSITORY_PATH/ios_app"

echo "=== ci_post_clone: npm ci (ios_app) ==="
cd "$APP_ROOT"
npm ci || npm install

echo "=== ci_post_clone: cap sync ios ==="
npm run cap:sync:ios

echo "=== ci_post_clone: link node_modules for SPM ==="
# Package.swift resolves ../../../node_modules -> ios_app/ios/node_modules
ln -sfn "$APP_ROOT/node_modules" "$APP_ROOT/ios/node_modules"

echo "=== ci_post_clone: done ==="
