import { defineConfig, devices } from '@playwright/test'
import { E2E_BACKEND_ORIGIN, E2E_FRONTEND_ORIGIN, E2E_FRONTEND_PORT } from './e2e/env'

/**
 * Phase 12 exit criteria: "A user can walk the Phase 3 mini question graph
 * from a mobile viewport end-to-end against the real backend." globalSetup
 * seeds a scratch sqlite DB and boots the real FastAPI backend (see
 * e2e/global-setup.ts); this config boots the real Vite dev server against
 * it (VITE_BACKEND_ORIGIN points the dev proxy at the seeded backend
 * instead of a developer's local :8000). Default project viewport is a
 * phone size, matching the mobile-first requirement.
 */
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  // All specs share ONE dev server + ONE backend + ONE sqlite file (see
  // global-setup.ts) — running spec files in parallel workers contends for
  // that single Vite dev server's cold module-transform pass and can push
  // first paint past a normal assertion timeout. Serial execution matches
  // the shared-infra reality here; it's not a per-test correctness issue.
  workers: 1,
  retries: 0,
  use: {
    baseURL: E2E_FRONTEND_ORIGIN,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'mobile',
      use: { ...devices['iPhone 13'] },
    },
  ],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${E2E_FRONTEND_PORT} --strictPort`,
    url: E2E_FRONTEND_ORIGIN,
    reuseExistingServer: !process.env.CI,
    env: { VITE_BACKEND_ORIGIN: E2E_BACKEND_ORIGIN },
  },
})
