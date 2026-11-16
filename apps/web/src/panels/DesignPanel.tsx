/** Design editor panel: name, arm length, battery placement, powertrain
  picks, frame geometry, drag. All numeric inputs are SI. */

import { useDesignStore } from '../state/designStore'
import { useComponents, useDesignsList, usePreview, useSaveDesign } from '../services/queries'
import { batteryPart } from '../state/designStore'
import { NumberField, SectionTitle, SelectField, TextField } from './fields'
import { analyzeGeometry } from '../editor/geometryChecks'

export function DesignPanel() {
  const { design, designId, setSnapshot, setName, setArmLength, setBatteryPosition,
          setBatteryMass, setPowertrain, setFrame, setDrag,
          setPlateDimensions, setMountPosition, removeMount } = useDesignStore()
  const components = useComponents()
  const designsList = useDesignsList()
  const preview = usePreview(design)
  const save = useSaveDesign()

  const battery = batteryPart(design)
  const motorOpts = (components.data?.motors ?? []).map((m) => ({
    value: m.id,
    label: `${m.name}${m.estimated ? ' (est.)' : ''}`,
  }))
  const propOpts = (components.data?.propellers ?? []).map((p) => ({
    value: p.id,
    label: `${p.name} (${p.diameter_in}x${p.pitch_in})`,
  }))
  const battOpts = (components.data?.batteries ?? []).map((b) => ({
    value: b.id,
    label: `${b.name}${b.estimated ? ' (est.)' : ''}`,
  }))
  const escOpts = (components.data?.escs ?? []).map((e) => ({
    value: e.id,
    label: `${e.name}${e.estimated ? ' (est.)' : ''}`,
  }))
  const matOpts = (components.data?.materials ?? []).map((m) => ({ value: m.id, label: m.name }))

  const armLength = design.frame?.arm_length_m ?? 0.25
  const selectedProp = components.data?.propellers.find(
    (p) => p.id === design.powertrain?.propeller_id,
  )
  const constraints = analyzeGeometry(design, selectedProp?.diameter_in)

  const onSave = async () => {
    const saved = await save.mutateAsync(design)
    setSnapshot(saved.snapshot, saved.id)
  }

  const loadDesign = async (id: number) => {
    const rec = await fetch(`/api/designs/${id}`).then((r) => r.json())
    setSnapshot(rec.snapshot, rec.id)
  }

  return (
    <div className="space-y-5 p-3">
      <section>
        <SectionTitle>Saved designs</SectionTitle>
        <select
          className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
          value={designId ?? ''}
          onChange={(e) => {
            const id = parseInt(e.target.value, 10)
            if (Number.isFinite(id)) void loadDesign(id)
          }}
        >
          <option value="">— load a design —</option>
          {(designsList.data ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              #{d.id} {d.name}
            </option>
          ))}
        </select>
      </section>

      <section className="space-y-2">
        <SectionTitle>Design</SectionTitle>
        <TextField label="name" value={design.name} onChange={setName} />
        <NumberField
          label="arm length"
          unit="m"
          value={armLength}
          step={0.01}
          min={0.05}
          max={2}
          onChange={(v) => setArmLength(v)}
        />
        {design.rotors.length !== 4 && (
          <p className="text-xs text-amber-400">
            Only Quad-X arm scaling is implemented. Rotor assemblies are locked for other layouts.
          </p>
        )}
        <NumberField
          label="drag CdA"
          unit="m²"
          value={design.drag_cd_a_m2 ?? 0}
          step={0.005}
          min={0}
          onChange={(v) => setDrag(v > 0 ? v : null)}
        />
      </section>

      <section className="space-y-2">
        <SectionTitle>Battery placement</SectionTitle>
        {battery ? (
          <>
            {battery.mount_id && <p className="text-xs text-amber-400">
              Battery is mounted. Edit the mount coordinates in Frame settings.
            </p>}
            <NumberField label="x" unit="m" value={battery.position_m[0]} step={0.005}
              onChange={(v) => setBatteryPosition([v, battery.position_m[1], battery.position_m[2]])} />
            <NumberField label="y" unit="m" value={battery.position_m[1]} step={0.005}
              onChange={(v) => setBatteryPosition([battery.position_m[0], v, battery.position_m[2]])} />
            <NumberField label="z" unit="m" value={battery.position_m[2]} step={0.005}
              onChange={(v) => setBatteryPosition([battery.position_m[0], battery.position_m[1], v])} />
            <NumberField label="mass" unit="kg" value={battery.mass_kg} step={0.05} min={0.05}
              onChange={setBatteryMass} />
          </>
        ) : (
          <p className="text-xs text-slate-500">no battery part in this design</p>
        )}
      </section>

      <section className="space-y-2">
        <SectionTitle>Powertrain (evidence DB)</SectionTitle>
        <SelectField label="motor" value={design.powertrain?.motor_id ?? ''} options={motorOpts}
          onChange={(v) => design.powertrain && setPowertrain({ ...design.powertrain, motor_id: v })} />
        <SelectField label="propeller" value={design.powertrain?.propeller_id ?? ''} options={propOpts}
          onChange={(v) => design.powertrain && setPowertrain({ ...design.powertrain, propeller_id: v })} />
        <SelectField label="ESC" value={design.powertrain?.esc_id ?? ''} options={escOpts}
          onChange={(v) => design.powertrain && setPowertrain({ ...design.powertrain, esc_id: v })} />
        <SelectField label="battery" value={design.powertrain?.battery_id ?? ''} options={battOpts}
          onChange={(v) => design.powertrain && setPowertrain({ ...design.powertrain, battery_id: v })} />
        {!design.powertrain && (
          <p className="text-xs text-amber-500">no powertrain — only ideal-actuator scenarios run</p>
        )}
      </section>

      <section className="space-y-2">
        <SectionTitle>Frame (structural check)</SectionTitle>
        <SelectField label="material" value={design.frame?.material_id ?? ''} options={matOpts}
          onChange={(v) =>
            setFrame({
              ...design.frame,
              arm_length_m: armLength,
              tube_od_m: design.frame?.tube_od_m ?? 0.012,
              tube_id_m: design.frame?.tube_id_m ?? 0.010,
              material_id: v,
            })
          } />
        {design.frame && (
          <>
            <NumberField label="tube OD" unit="m" value={design.frame.tube_od_m} step={0.001} min={0.003}
              onChange={(v) => setFrame({ ...design.frame!, tube_od_m: v, arm_length_m: armLength })} />
            <NumberField label="tube ID" unit="m" value={design.frame.tube_id_m} step={0.001} min={0.002}
              onChange={(v) => setFrame({ ...design.frame!, tube_id_m: v, arm_length_m: armLength })} />
          </>
        )}
        {design.frame && (
          <div className="space-y-2 border-t border-slate-800 pt-2">
            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input type="checkbox" checked={!!design.frame.plate_dimensions_m}
                aria-label="Dimensioned center plate"
                onChange={(e) => setPlateDimensions(e.target.checked ? [0.16, 0.16, 0.03] : null)}
                className="accent-cyan-500" />
              Dimensioned center plate (visual only)
            </label>
            {design.frame.plate_dimensions_m &&
              (['X width', 'Y depth', 'Z thickness'] as const).map((label, index) => (
                <NumberField key={label} label={`plate ${label}`} unit="m"
                  value={design.frame!.plate_dimensions_m![index]} min={0.001} step={0.005}
                  onChange={(v) => {
                    const current = design.frame!.plate_dimensions_m!
                    const next = [...current] as [number, number, number]
                    next[index] = v
                    setPlateDimensions(next)
                  }} />
              ))}
            <p className="text-[10px] text-slate-500">
              Tube outside diameter controls the rendered arm thickness. Plate geometry
              does not change the existing measured frame mass or inertia.
            </p>
            <SectionTitle>Frame mounting points</SectionTitle>
            {(design.frame.mount_points ?? []).map((mount) => (
              <div key={mount.id} className="space-y-1 rounded border border-slate-800 p-2">
                <div className="flex items-center justify-between text-xs text-slate-300">
                  <span>{mount.id}</span>
                  <button type="button" onClick={() => removeMount(mount.id)}
                    aria-label={`Remove ${mount.id}`}
                    className="text-rose-300">Remove</button>
                </div>
                {(['X', 'Y', 'Z'] as const).map((axis, i) => (
                  <NumberField key={axis} label={`${mount.id} ${axis}`} unit="m"
                    value={mount.position_m[i]} step={0.005}
                    onChange={(v) => {
                      const next = [...mount.position_m] as [number, number, number]
                      next[i] = v
                      setMountPosition(mount.id, next)
                    }} />
                ))}
              </div>
            ))}
            {(design.frame.mount_points ?? []).length === 0 && (
              <p className="text-xs text-slate-500">
                Select a battery or payload in the 3D component inspector,
                then create a mount at its CoG.
              </p>
            )}
          </div>
        )}
        {!design.frame && (
          <p className="text-xs text-slate-500">no frame — structural monitor skipped (flagged)</p>
        )}
      </section>

      <section className="space-y-2" aria-label="Geometry preflight">
        <SectionTitle>Geometry preflight</SectionTitle>
        {constraints.length === 0
          ? <p className="text-xs text-emerald-400">
              No detectable geometry inconsistencies in the limited checks below.
            </p>
          : constraints.map((issue, i) => (
              <p key={i} className={`text-xs ${
                issue.severity === 'error' ? 'text-rose-300'
                  : issue.severity === 'warning' ? 'text-amber-300'
                    : 'text-slate-400'
              }`}>
                [{issue.severity.toUpperCase()}] {issue.message}
              </p>
            ))}
        <p className="text-[10px] text-slate-500">
          Preliminary dimension/data checks only. No CAD collision solving,
          rotor-interaction CFD, structural certification or flight-worthiness verdict.
        </p>
      </section>
      <section className="space-y-2">
        <SectionTitle>Preview (from physics core)</SectionTitle>
        {preview.data && (
          <div className="space-y-1 text-xs text-slate-300">
            <p>
              mass <span className="font-mono">{preview.data.mass_kg.toFixed(3)}</span> kg · CoG{' '}
              <span className="font-mono">
                ({preview.data.cog_m.map((v) => v.toFixed(3)).join(', ')})
              </span>{' '}
              m
            </p>
            <p>
              principal moments{' '}
              <span className="font-mono">
                {preview.data.principal_moments_kg_m2.map((v) => v.toFixed(4)).join(' / ')}
              </span>{' '}
              kg·m²
            </p>
            {preview.data.hover_trim_error ? (
              <p className="text-rose-400">trim: {preview.data.hover_trim_error}</p>
            ) : (
              <p className="text-emerald-500">
                hover trim: {preview.data.hover_trim_thrusts_n?.map((t) => t.toFixed(2)).join(' / ')} N
              </p>
            )}
          </div>
        )}
        {preview.isError && (
          <p className="text-xs text-rose-400">preview error: {(preview.error as Error).message}</p>
        )}
      </section>

      <button
        className="w-full rounded bg-slate-700 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-slate-600 disabled:opacity-50"
        onClick={() => void onSave()}
        disabled={save.isPending}
      >
        {save.isPending ? 'saving…' : designId != null ? 'Save design' : 'Save as new design'}
      </button>
      {save.isError && (
        <p className="text-xs text-rose-400">save failed: {(save.error as Error).message}</p>
      )}
    </div>
  )
}
