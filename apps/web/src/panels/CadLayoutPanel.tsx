import { useMutation } from '@tanstack/react-query'
import { api } from '../services/api'
import { useSaveDesign } from '../services/queries'
import type { DroneDesign, Vec3 } from '../types/api'

interface LayoutPreview {
  snapshot: DroneDesign
  changes: { item: string; name: string; from_m: Vec3; to_m: Vec3 }[]
}

export function CadLayoutPanel({ id, revision }: { id: number; revision: number }) {
  const path = `/designs/${id}/revisions/${revision}`
  const save = useSaveDesign()
  const preview = useMutation({
    mutationFn: (file: File) => api.postDxf<LayoutPreview>(`${path}/layout-preview`, file),
  })
  return (
    <section aria-label="CAD layout" className="space-y-2 rounded border border-slate-700 p-2 text-xs">
      <a className="text-cyan-300 underline" href={`/api${path}/layout.dxf`} download>
        Download revision {revision} CAD layout (DXF)
      </a>
      <p className="text-slate-400">Edit body-frame points in metres. Move related rotor and component
        positions together. Mounted parts follow their mount.</p>
      <label className="block text-slate-300">
        Preview edited DXF
        <input type="file" accept=".dxf" disabled={preview.isPending || save.isPending}
          className="mt-1 block w-full text-xs" onChange={(event) => {
            const file = event.target.files?.[0]
            if (!file) return
            save.reset()
            preview.mutate(file)
            event.target.value = ''
          }} />
      </label>
      {preview.isPending && <p role="status">Reading CAD layout…</p>}
      {(preview.error || save.error) && <p role="alert" className="text-rose-300">{(preview.error ?? save.error)?.message}</p>}
      {preview.data && (
        <div className="space-y-1">
          <p>{preview.data.changes.length} position {preview.data.changes.length === 1 ? 'change' : 'changes'} from revision {revision}</p>
          <ul className="max-h-40 overflow-auto text-slate-300">
            {preview.data.changes.map((change, i) => <li key={i}>{change.item} {change.name} ·
              {' '}{change.from_m.join(', ')} → {change.to_m.join(', ')} m</li>)}
          </ul>
          <button type="button" className="rounded border border-slate-600 px-2 py-1"
            disabled={!preview.data.changes.length || save.isPending || save.isSuccess}
            onClick={() => save.mutate(preview.data.snapshot)}>Save CAD changes as new design</button>
          {save.data && <p role="status">Saved design #{save.data.id} · {save.data.name}</p>}
        </div>
      )}
    </section>
  )
}
