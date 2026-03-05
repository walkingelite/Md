import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.markreader.app',
  appName: 'MarkReader',
  webDir: 'dist',
  server: {
    // Use https scheme on Android so browser APIs (clipboard, etc.) work correctly
    androidScheme: 'https',
  },
  plugins: {
    // Splash screen and status bar can be configured here when added
  },
}

export default config
