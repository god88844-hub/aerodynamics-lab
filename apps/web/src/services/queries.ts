/** TanStack Query hooks for the AeroForge API. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type {
  ComponentsResponse,
  DesignPreview,
  DesignRecord,
  DesignSummary,
  DroneDesign,
  SimulationResult,
} from '../types/api'

export function useComponents() {
  return useQuery({
    queryKey: ['components'],
    queryFn: () => api.get<ComponentsResponse>('/components'),
    staleTime: Infinity,
  })
}

export function useDesignsList() {
  return useQuery({
    queryKey: ['designs'],
    queryFn: () => api.get<DesignSummary[]>('/designs'),
  })
}

export function useReferenceDesign() {
  return useQuery({
    queryKey: ['reference-design'],
    queryFn: () => api.get<{ name: string; snapshot: DroneDesign }>('/designs/reference'),
    staleTime: Infinity,
  })
}

export function useDesign(id: number | null) {
  return useQuery({
    queryKey: ['design', id],
    queryFn: () => api.get<DesignRecord>(`/designs/${id}`),
    enabled: id !== null,
  })
}

/** Editor preview: mass properties + principal axes + trim feasibility.
  The design object is part of the key, so edits re-run the preview. */
export function usePreview(design: DroneDesign) {
  return useQuery({
    queryKey: ['preview', design],
    queryFn: () => api.post<DesignPreview>('/designs/preview', { snapshot: design }),
    staleTime: Infinity,
    retry: false,
  })
}

export function useSaveDesign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (design: DroneDesign & { id?: number | null }) => {
      if (design.id != null) {
        return api.put<DesignRecord>(`/designs/${design.id}`, { snapshot: design })
      }
      return api.post<DesignRecord>('/designs', { snapshot: design })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['designs'] }),
  })
}

export function useSimulate() {
  return useMutation({
    mutationFn: ({ designId, scenario, params }: { designId: number; scenario: string; params?: Record<string, unknown> }) =>
      api.post<SimulationResult>(`/designs/${designId}/simulate`, {
        scenario,
        params: params ?? {},
      }),
  })
}
