import { fileURLToPath } from 'node:url'

/** Shared between global-setup.ts (seeds + starts the backend) and
 * playwright.config.ts (starts the frontend dev server against it). One
 * scratch sqlite file per E2E run — never the developer's own Postgres dev
 * database, so running `npm run test:e2e` can't clobber real data. */
export const E2E_BACKEND_PORT = 8000
export const E2E_FRONTEND_PORT = 5173
export const E2E_DATABASE_URL = 'sqlite:///./var/e2e_test.db'
export const E2E_BACKEND_ORIGIN = `http://127.0.0.1:${E2E_BACKEND_PORT}`
export const E2E_FRONTEND_ORIGIN = `http://127.0.0.1:${E2E_FRONTEND_PORT}`
export const SEED_OUTPUT_PATH = fileURLToPath(new URL('./.seed-output.json', import.meta.url))
/** Phase 13's fixture lives under its own assessment year (2099-01, an
 * obvious non-real AY) so it can share the same scratch database as Phase
 * 12's fixture (above) without either one's questionnaire/tax_rule_set
 * versions colliding — see backend/scripts/seed_phase13_data.py. */
export const SEED_OUTPUT_PATH_PHASE13 = fileURLToPath(new URL('./.seed-output-phase13.json', import.meta.url))
