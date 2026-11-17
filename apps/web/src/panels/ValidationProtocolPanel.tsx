import { useRef, useState } from 'react'
import { api } from '../services/api'

interface ProtocolReport {
  protocol_id: string
  canonical_protocol_sha256: string
  matches_supplied_frozen_sha256: boolean
  readiness_status: string
  blockers: string[]
  independent_physical_accuracy_demonstrated: boolean
  decision_equivalent_to_physical_testing: boolean
  independently_approved: boolean
}

/** Metadata consistency audit only. Never authorizes physical testing. */
export function ValidationProtocolPanel() {
  const [protocolText, setProtocolText] = useState('')
  const [expectedHash, setExpectedHash] = useState('')
  const [manifestsText, setManifestsText] = useState('[]')
  const [report, setReport] = useState<ProtocolReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const latest = useRef(0)

  const invalidate = () => {
    latest.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }
  const submit = async () => {
    const request = ++latest.current
    setError(null)
    setReport(null)
    try {
      if (!protocolText.trim()) throw new Error('Enter a registered validation protocol JSON')
      const protocol = JSON.parse(protocolText) as unknown
      const manifests = JSON.parse(manifestsText || '[]') as unknown
      if (!protocol || typeof protocol !== 'object' || Array.isArray(protocol)) {
        throw new Error('Protocol must be a JSON object')
      }
      if (!Array.isArray(manifests)) throw new Error('Imported manifests must be a JSON array')
      const expected_frozen_sha256 = expectedHash.trim() || null
      if (expected_frozen_sha256 && !/^[0-9a-f]{64}$/.test(expected_frozen_sha256)) {
        throw new Error('Expected protocol hash must be 64 lowercase hexadecimal characters')
      }
      setRunning(true)
      const data = await api.post<ProtocolReport>('/components/validation-protocol-audit', {
        protocol, expected_frozen_sha256, imported_manifests: manifests,
      })
      if (latest.current === request) setReport(data)
    } catch (err) {
      if (latest.current === request) setError((err as Error).message)
    } finally {
      if (latest.current === request) setRunning(false)
    }
  }
  return (
    <section aria-label="Pre-registered physical validation protocol" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Physical validation preregistration
      </h3>
      <p className="text-[10px] text-amber-400">
        Audit frozen model identity, test hardware, sensors, uncertainty
        and whole-experiment holdouts. A matching hash cannot authenticate a
        physical test or certify flight readiness.
      </p>
      <label className="block text-xs">
        Validation protocol JSON
        <textarea aria-label="Validation protocol JSON" rows={5} value={protocolText}
          onChange={e => { invalidate(); setProtocolText(e.target.value) }}
          placeholder="Exact hardware, envelope and preregistered acceptance criteria"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <label className="block text-xs">
        Externally frozen protocol SHA-256 (optional)
        <input aria-label="Frozen protocol SHA-256" value={expectedHash}
          onChange={e => { invalidate(); setExpectedHash(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <label className="block text-xs">
        Imported M19 telemetry manifests JSON array
        <textarea aria-label="Imported telemetry manifests JSON" rows={3} value={manifestsText}
          onChange={e => { invalidate(); setManifestsText(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" disabled={running} onClick={() => { void submit() }}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Checking protocol…' : 'Audit physical validation protocol'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 rounded border border-slate-700 p-2 text-xs">
          <p className="font-semibold text-amber-300">
            {report.readiness_status.replaceAll('_', ' ')}
          </p>
          <p>Protocol: {report.protocol_id}</p>
          <p className="break-all font-mono text-[10px]">
            Canonical protocol SHA-256: {report.canonical_protocol_sha256}
          </p>
          <p>Frozen digest matches: {report.matches_supplied_frozen_sha256 ? 'yes' : 'no'}</p>
          <p>Independent physical accuracy demonstrated: {
            report.independent_physical_accuracy_demonstrated ? 'yes' : 'no'
          }</p>
          <p>Decision equivalent to physical testing: {
            report.decision_equivalent_to_physical_testing ? 'yes' : 'no'
          }</p>
          <p>Independent approval verified: {report.independently_approved ? 'yes' : 'no'}</p>
          <p>Blocking gaps: {report.blockers.length}</p>
          {report.blockers.length > 0 && (
            <ul className="list-inside list-disc text-[10px] text-amber-400">
              {report.blockers.map((reason, i) => <li key={i}>{reason}</li>)}
            </ul>
          )}
          <p className="text-[10px] text-slate-400">
            Declared measurement uncertainties are unauthenticated. No
            result authorizes physical testing or certifies an aircraft.
          </p>
        </div>
      )}
    </section>
  )
}
