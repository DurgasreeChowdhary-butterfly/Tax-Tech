/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Same-origin from the browser's point of view during dev — the
      // backend needs no CORS configuration, and the API base URL used by
      // the app (see src/api/client.ts) can stay a plain relative path.
      '/api': {
        target: process.env.VITE_BACKEND_ORIGIN ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/testSetup.ts'],
    exclude: ['**/node_modules/**', '**/e2e/**'],
  },
})
