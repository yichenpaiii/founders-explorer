import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export default defineConfig(async ({ mode }) => {
  const devVars = mode === 'development' ? loadDevVars() : {}
  injectIntoProcess(devVars)

  if (mode === 'development') {
    await printSupabaseSnapshot(devVars)
  }

  return {
    envPrefix: 'SUPABASE_',
    define: {
      __SUPABASE_DEV_VARS__: JSON.stringify(devVars),
    },
    plugins: [react()],
  }
})

function loadDevVars() {
  const filePath = resolve(process.cwd(), '.dev.vars')
  if (!existsSync(filePath)) return {}

  const vars = {}
  const contents = readFileSync(filePath, 'utf8')
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const eqIdx = line.indexOf('=')
    if (eqIdx === -1) continue
    const key = line.slice(0, eqIdx).trim()
    const value = stripQuotes(line.slice(eqIdx + 1).trim())
    if (key) vars[key] = value
  }
  return vars
}

function stripQuotes(value) {
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith('\'') && value.endsWith('\''))) {
    return value.slice(1, -1)
  }
  return value
}

function injectIntoProcess(vars) {
  for (const [key, value] of Object.entries(vars)) {
    if (!(key in process.env)) {
      process.env[key] = value
    }
  }
}

async function printSupabaseSnapshot(vars) {
  const url = vars.SUPABASE_URL
  const anonKey = vars.SUPABASE_ANON_KEY
  if (!url || !anonKey) {
    console.warn('[supabase] Missing SUPABASE_URL or SUPABASE_ANON_KEY; skipping snapshot')
    return
  }

  try {
    const endpoint = new URL('/rest/v1/courses_search_view', url.replace(/\/$/, ''))
    endpoint.searchParams.set('select', '*')

    const response = await fetch(endpoint, {
      headers: {
        apikey: anonKey,
        Authorization: `Bearer ${anonKey}`,
      },
    })

    if (!response.ok) {
      const errText = await safeReadText(response)
      console.error(`[supabase] Snapshot fetch failed: HTTP ${response.status} ${response.statusText}${errText ? ` - ${errText}` : ''}`)
      return
    }

    const data = await response.json()
    const total = Array.isArray(data) ? data.length : 0
    console.log(`[supabase] Retrieved ${total} rows from courses_search_view`)
    console.log(JSON.stringify(data, null, 2))
  } catch (err) {
    console.error('[supabase] Snapshot fetch threw an error:', err?.message || err)
  }
}

async function safeReadText(response) {
  try {
    return await response.text()
  } catch (err) {
    return ''
  }
}
