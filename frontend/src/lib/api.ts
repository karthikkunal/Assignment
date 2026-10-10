import type {
  AppConfig,
  DashboardData,
  DiscoveryRun,
  FilesystemReport,
  FilesystemScanInput,
  HealthData,
  ScanSchedule,
  ScheduleInput,
  TLSReport,
  TLSScanInput,
} from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthData>('/health'),
  config: () => request<AppConfig>('/config'),
  dashboard: () => request<DashboardData>('/dashboard'),
  runs: () => request<DiscoveryRun[]>('/runs?limit=500'),
  filesystemReport: (runId: string) =>
    request<FilesystemReport>(`/reports/filesystem/${runId}`),
  tlsReport: (runId: string) => request<TLSReport>(`/reports/tls/${runId}`),
  startFilesystem: (input: FilesystemScanInput) =>
    request<DiscoveryRun>('/runs/filesystem', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  startTLS: (input: TLSScanInput) =>
    request<DiscoveryRun>('/runs/tls', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  schedules: () => request<ScanSchedule[]>('/schedules'),
  createSchedule: (input: ScheduleInput) =>
    request<ScanSchedule>('/schedules', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  toggleSchedule: (scheduleId: string, enabled: boolean) =>
    request<ScanSchedule>(`/schedules/${scheduleId}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  deleteSchedule: (scheduleId: string) =>
    request<void>(`/schedules/${scheduleId}`, { method: 'DELETE' }),
}