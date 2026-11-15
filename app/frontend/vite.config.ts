/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// Config lives in the repo-root .env (ADR 0004); VERSION is the single version source (ADR 0005).
const repoRoot = fileURLToPath(new URL('../..', import.meta.url))
const version = readFileSync(new URL('../../VERSION', import.meta.url), 'utf-8').trim()

// Defaults come from the settings schema that configure.bat also uses, so they live in one place.
type Schema = { groups: { settings: { name: string; default: string }[] }[] }
const schema = JSON.parse(
  readFileSync(new URL('../../scripts/settings.schema.json', import.meta.url), 'utf-8'),
) as Schema
const defaults = Object.fromEntries(schema.groups.flatMap((g) => g.settings.map((s) => [s.name, s.default])))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repoRoot, 'ARCHEION_')
  const backendPort = Number(env.ARCHEION_PORT || defaults.ARCHEION_PORT)
  const port = Number(env.ARCHEION_FRONTEND_PORT || defaults.ARCHEION_FRONTEND_PORT)
  const server = {
    host: '127.0.0.1',
    port,
    strictPort: true,
    // One origin for the browser: no CORS, and the SameSite=Strict session cookie just works.
    proxy: { '/api': { target: `http://127.0.0.1:${backendPort}` } },
  }
  return {
    plugins: [react()],
    define: { __APP_VERSION__: JSON.stringify(version) },
    server,
    preview: server,
    build: { chunkSizeWarningLimit: 4000 },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
