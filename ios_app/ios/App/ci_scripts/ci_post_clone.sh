#!/bin/sh
# Xcode Cloud post-clone — install Capacitor deps so SPM local-path packages resolve.
#
# Package.swift (ios_app/ios/App/CapApp-SPM/Package.swift) references
# ../../../node_modules. In the Xcode Cloud container, SPM resolves this relative
# to the workspace dir (ios_app/ios/App/), so it lands at ios_app/node_modules —
# exactly where `npm ci` installs. No symlink needed.
set -e

echo "=== ci_post_clone: locating node ==="
# Xcode Cloud runners ship Homebrew. node may or may not already be on PATH.
if ! command -v node >/dev/null 2>&1; then
  echo "node not on PATH; installing via Homebrew"
  brew install node@22
  export PATH="$(brew --prefix node@22)/bin:$PATH"
fi

# Ensure brew's node bin is on PATH even if node@22 was already installed.
if command -v brew >/dev/null 2>&1; then
  export PATH="$(brew --prefix)/bin:$PATH"
  if brew --prefix node@22 >/dev/null 2>&1; then
    export PATH="$(brew --prefix node@22)/bin:$PATH"
  fi
fi

echo "node: $(command -v node || echo MISSING)"
node --version
npm --version

APP_ROOT="$CI_PRIMARY_REPOSITORY_PATH/ios_app"

echo "=== ci_post_clone: npm ci (ios_app) ==="
cd "$APP_ROOT"
npm ci || npm install

echo "=== ci_post_clone: cap sync ios ==="
npm run cap:sync:ios

echo "=== ci_post_clone: verify SPM deps present ==="
ls -d node_modules/@capacitor/app node_modules/@capacitor/browser || echo "WARN: capacitor node_modules missing"

echo "=== ci_post_clone: done ==="
