/**
 * PuranGPT iOS — Runtime config injection
 * Place this script tag BEFORE app.js in index.html when building for iOS.
 *
 * In the iOS app the frontend is a local file (file://), so API calls
 * to '' (relative) or 'http://localhost:8000' both fail.
 * This file sets CONFIG.apiUrl to your deployed Railway backend URL.
 *
 * USAGE: After deploying to Railway, replace RAILWAY_URL below with your actual URL.
 */

// Injected before app.js loads — overrides localStorage default
(function() {
  // ← Replace with your Railway URL after deployment
  const DEPLOYED_API = 'https://purangpt-production.up.railway.app';

  // Only override when running inside Capacitor (iOS/Android native shell)
  const isCapacitor = window.Capacitor !== undefined ||
                      window.location.protocol === 'capacitor:' ||
                      window.location.protocol === 'ionic:';

  if (isCapacitor && !localStorage.getItem('purangpt_api_url')) {
    localStorage.setItem('purangpt_api_url', DEPLOYED_API);
    console.log('[PuranGPT iOS] API pointed at:', DEPLOYED_API);
  }
})();
