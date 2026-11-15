/** API shapes (mirrors aeroforge_schemas). Units are SI; names carry units. */

export type Vec3 = [number, number, number]

export interface PartInstance {
  name: string
  mass_kg: number
  position_m: Vec3
  inertia_about_own_cog_kg_m2?: number[][] | null
}

export interface RotorInstance {
  position_m: Vec3
  spin_direction: 1 | -1
  motor_id?: string | null
  propeller_id?: string | null
}

export interface PowertrainConfig {
  motor_id: string
  propeller_id: string
  esc_id: string
  battery_id: string
}

export interface FrameSpec {
  arm_length_m: number
  tube_od_m: number
  tube_id_m: number
  material_id: string
}

export interface DroneDesign {
  schema_version: '0.1'
  name: string
  parts: PartInstance[]
  rotors: RotorInstance[]
  powertrain?: PowertrainConfig | null
  frame?: FrameSpec | null
  drag_cd_a_m2?: number | null
  rotor_torque_per_thrust_n_m_per_n: number
  notes?: string | null
}

export interface DesignSummary {
  id: number
  name: string
  created_at: string
  updated_at: string
}

export interface DesignRecord {
  id: number
  name: string
  snapshot: DroneDesign
  updated_at?: string
}

export interface ComponentSummary {
  id: string
  name: string
  estimated: boolean
  uncertainty_pct: number
  source: string
  mass_kg: number | null
  diameter_in?: number
  pitch_in?: number
  capacity_ah?: number
  cells_series?: number
  max_continuous_current_a?: number
}

export interface MaterialSummary {
  id: string
  name: string
  yield_strength_pa: number | null
  uncertainty_pct: number
}

export interface ComponentsResponse {
  motors: ComponentSummary[]
  propellers: ComponentSummary[]
  batteries: ComponentSummary[]
  escs: ComponentSummary[]
  materials: MaterialSummary[]
}

export interface DesignPreview {
  mass_kg: number
  cog_m: Vec3
  inertia_kg_m2: number[][]
  principal_moments_kg_m2: number[]
  principal_axes: number[][]
  hover_trim_thrusts_n: number[] | null
  hover_trim_error: string | null
  n_rotors: number
}

export interface FailureEvent {
  t_s: number | null
  kind: string
  critical: boolean
  message: string
}

export interface Telemetry {
  t: number[]
  x: number[]
  y: number[]
  z: number[]
  vz: number[]
  motor_thrusts_n: number[][]
  motor_current_a?: number[][]
  v_bus_v?: number[]
  soc_pct?: number[]
  altitude_accel_cmd_m_s2?: number[]
  total_power_w?: number[]
  cell_voltage_v?: number[]
}

export interface TrustEntry {
  status?: string
  caveat?: string
  evidence?: string
  source?: string
  notes?: string
  [key: string]: unknown
}

export interface SimulationResult {
  simulation_id?: number
  design_id?: number
  scenario: string
  status: 'completed' | 'failed'
  error?: string
  physics_version?: string
  design?: Record<string, unknown>
  results?: Record<string, number | null>
  mission?: { profile: string; duration_s: number; aborted: boolean; abort_event: string | null }
  hover_point?: Record<string, unknown>
  endurance?: Record<string, number | null>
  benchmarks?: { name: string; status: string; metrics: Record<string, number>; notes: string }[]
  events?: FailureEvent[]
  success?: Record<string, boolean>
  telemetry?: Telemetry | null
  trustworthiness?: Record<string, TrustEntry | string>
}
