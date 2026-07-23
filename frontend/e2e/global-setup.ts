import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { existsSync, mkdirSync, openSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { E2E_BACKEND_ORIGIN, E2E_BACKEND_PORT, E2E_DATABASE_URL, SEED_OUTPUT_PATH, SEED_OUTPUT_PATH_PHASE13 } from './env'

const backendDir = path.resolve(fileURLToPath(new URL('.', import.meta.url)), '../../backend')

function resolvePython(): string {
  const venvPython = path.join(backendDir, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  return existsSync(venvPython) ? venvPython : 'python'
}

async function waitForHealth(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${E2E_BACKEND_ORIGIN}/api/v1/health`)
      if (response.ok) return
    } catch {
      // Backend not accepting connections yet — keep polling.
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`Backend at ${E2E_BACKEND_ORIGIN} did not become healthy within ${timeoutMs}ms`)
}

/**
 * Seeds a scratch sqlite database with two independent fixtures — the Phase
 * 12 mini question graph (backend/scripts/seed_dev_data.py, used by
 * questionnaire.spec.ts) and the Phase 13 extraction-review/regime-
 * comparison/tax-summary fixture (backend/scripts/seed_phase13_data.py, used
 * by guided-journey.spec.ts) — then boots the real FastAPI backend against
 * that same database, so every E2E spec exercises the actual backend rather
 * than a mock (docs/IMPLEMENTATION_PLAN.md's "against the real backend" exit
 * criteria). The frontend dev server itself is started separately via
 * Playwright's own `webServer` option in playwright.config.ts.
 */
export default async function globalSetup(): Promise<() => Promise<void>> {
  const python = resolvePython()
  const env = { ...process.env, DATABASE_URL: E2E_DATABASE_URL, PYTHONPATH: '.' }

  mkdirSync(path.join(backendDir, 'var'), { recursive: true })

  const seedOutput = execFileSync(python, ['scripts/seed_dev_data.py'], { cwd: backendDir, env, encoding: 'utf-8' })
  writeFileSync(SEED_OUTPUT_PATH, seedOutput.trim())

  const phase13SeedOutput = execFileSync(python, ['scripts/seed_phase13_data.py'], { cwd: backendDir, env, encoding: 'utf-8' })
  writeFileSync(SEED_OUTPUT_PATH_PHASE13, phase13SeedOutput.trim())

  const logFd = openSync(path.join(backendDir, 'var', 'e2e_backend.log'), 'w')
  const backend: ChildProcess = spawn(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(E2E_BACKEND_PORT)],
    { cwd: backendDir, env, stdio: ['ignore', logFd, logFd] },
  )

  try {
    await waitForHealth(30_000)
  } catch (error) {
    backend.kill()
    throw error
  }

  return async () => {
    if (backend.pid && process.platform === 'win32') {
      try {
        execFileSync('taskkill', ['/pid', String(backend.pid), '/T', '/F'], { stdio: 'ignore' })
      } catch {
        // Already exited (e.g. it crashed mid-run) — nothing left to kill.
      }
    } else {
      backend.kill()
    }
  }
}
