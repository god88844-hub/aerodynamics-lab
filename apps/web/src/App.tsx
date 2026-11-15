import { useEffect, useState } from 'react'

interface Health {
  status: string
  service: string
  version: string
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Health) => setHealth(data))
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: 32 }}>
      <h1>AeroForge</h1>
      <p>Physics-based drone simulation lab</p>
      <p style={{ color: '#64748b' }}>
        Every result will carry a best estimate, uncertainty, credibility rating, and caveats
        (NASA-STD-7009 / ASME V&amp;V 10). Multi-rotor only in v1.
      </p>
      {health && (
        <p style={{ color: '#16a34a' }}>
          API: {health.status} — {health.service} v{health.version}
        </p>
      )}
      {error && <p style={{ color: 'crimson' }}>API unreachable: {error}</p>}
    </main>
  )
}
