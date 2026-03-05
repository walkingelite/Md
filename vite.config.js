import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // './' base is required for Capacitor native WebViews (iOS/Android)
  // assets must be loaded relative, not from root '/'
  base: './',
})
