/** Small shared form controls for the editor panels. */

export function NumberField({ label, value, onChange, step = 0.01, min, max, unit }: {
  label: string
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
  unit?: string
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-400">
        {label} {unit && <span className="text-slate-600">[{unit}]</span>}
      </span>
      <input
        type="number"
        className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-right text-slate-200 focus:border-cyan-600 focus:outline-none"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => {
          const v = parseFloat(e.target.value)
          if (Number.isFinite(v)) onChange(v)
        }}
      />
    </label>
  )
}

export function TextField({ label, value, onChange }: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-400">{label}</span>
      <input
        type="text"
        className="w-44 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200 focus:border-cyan-600 focus:outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}

export function SelectField({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-400">{label}</span>
      <select
        className="w-44 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200 focus:border-cyan-600 focus:outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">{children}</h3>
}
