import type { CapacitorConfig } from '@capacitor/cli';

const isLocal = process.env.CAP_ENV === 'local';

const config: CapacitorConfig = {
  appId: 'com.fcpuru95.purangpt',
  appName: 'PuranGPT',
  webDir: 'out',
  server: isLocal
    ? {
        url: 'http://localhost:3000',
        cleartext: true,
      }
    : {
        url: 'https://purangpt.com',
        cleartext: false,
        androidScheme: 'https',
      },
  ios: {
    contentInset: 'automatic',
    backgroundColor: '#000000',
    allowsLinkPreview: false,
    preferredContentMode: 'mobile',
    // Persist cookies across app restarts — critical for auth state
    limitsNavigationsToAppBoundDomains: false,
  },
  android: {
    backgroundColor: '#000000',
    allowMixedContent: false,
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      launchShowDuration: 1200,
      backgroundColor: '#131313',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
    },
  },
};

export default config;
