#!/bin/bash
set -e

echo "Building iOS Web Assets with Next.js..."

# Navigate to Next.js project
cd ../purangpt-next

# Install dependencies if needed
npm install

# Build Next.js with static export
# Inject the Railway production URL so the iOS app knows where to talk to
export NEXT_PUBLIC_API_URL="https://purangpt-production.up.railway.app"
npm run build

echo "Next.js built successfully to purangpt-next/out!"
echo "Assets ready for Capacitor sync."
