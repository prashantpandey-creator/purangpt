#!/bin/bash
set -e

echo "Building iOS Web Assets..."

# Create fresh www directory
rm -rf www
mkdir www

# Copy all frontend files
cp -r ../frontend/* www/

# Copy the iOS config injection script
cp ios_config.js www/ios_config.js

# Rewrite absolute paths to relative paths for Capacitor
# (e.g. /static/style.css -> style.css, /static/app.js -> app.js)
sed -i '' 's|/static/||g' www/index.html

# Inject ios_config.js right before app.js
sed -i '' 's|<script src="app.js"></script>|<script src="ios_config.js"></script>\n  <script src="app.js"></script>|g' www/index.html

echo "Assets copied to www. Ready for Capacitor sync."
