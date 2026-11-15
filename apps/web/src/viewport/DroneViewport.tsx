/** 3D viewport: design model, CoG/principal axes, flight path telemetry,
  orbit controls. Scene mapping: world (x, y, z-up) -> scene (x, z, -y). */

import { Grid, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import type { DroneDesign, SimulationResult, Vec3 } from '../types/api'
import { DroneModel } from './DroneModel'

function FlightPath({ telemetry }: { telemetry: NonNullable<SimulationResult['telemetry']> }) {
  const n = telemetry.t.length
  if (n === 0) return null
  const step = Math.max(1, Math.floor(n / 400))
  const points: [number, number, number][] = []
  for (let i = 0; i < n; i += step) {
    points.push([telemetry.x[i], telemetry.z[i], -telemetry.y[i]])
  }
  const last = points[points.length - 1]
  const first = points[0]
  return (
    <group>
      <Line points={points} color="#22d3ee" lineWidth={2} />
      <mesh position={first}>
        <sphereGeometry args={[0.03, 12, 12]} />
        <meshStandardMaterial color="#22c55e" />
      </mesh>
      <mesh position={last}>
        <sphereGeometry args={[0.03, 12, 12]} />
        <meshStandardMaterial color="#f43f5e" />
      </mesh>
    </group>
  )
}

export function DroneViewport({ design, cog, principalAxes, result }: {
  design: DroneDesign
  cog: Vec3
  principalAxes: number[][] | null
  result: SimulationResult | null
}) {
  const scale = 4 // grid spans ±4 m around the drone
  return (
    <Canvas camera={{ position: [1.6, 1.2, 2.2], fov: 45 }} shadows={false}>
      <color attach="background" args={['#0b1120']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 6, 2]} intensity={1.2} />
      <Grid
        args={[scale * 2, scale * 2]}
        cellSize={0.25}
        cellThickness={0.5}
        sectionSize={1}
        sectionThickness={1}
        cellColor="#1e293b"
        sectionColor="#334155"
        infiniteGrid={false}
        fadeDistance={30}
      />
      <DroneModel design={design} cog={cog} principalAxes={principalAxes} />
      {result?.telemetry && <FlightPath telemetry={result.telemetry} />}
      <OrbitControls makeDefault />
    </Canvas>
  )
}
