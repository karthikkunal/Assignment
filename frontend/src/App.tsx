import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, FolderSearch, RadioTower, ShieldCheck } from 'lucide-react'
import { lazy, startTransition, Suspense, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { ScanDialog } from './components/ScanDialog'
import { SchedulesDialog } from './components/SchedulesDialog'
import { LoadingState } from './components/ui'
import { api } from './lib/api'
import type { FilesystemScanInput, ScanType, TLSScanInput } from './lib/types'

const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const FilesystemReportPage = lazy(() =>
  import('./pages/FilesystemReportPage').then((module) => ({
    default: module.FilesystemReportPage,
  })),
)
const TLSReportPage = lazy(() =>
  import('./pages/TLSReportPage').then((module) => ({ default: module.TLSReportPage })),
)

type ScanCommand =
  | { scanType: 'filesystem'; input: FilesystemScanInput }
  | { scanType: 'tls'; input: TLSScanInput }

function App() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [scanType, setScanType] = useState<ScanType | null>(null)
  const [schedulesOpen, setSchedulesOpen] = useState(false)
  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 5000,
    retry: 1,
  })
  const config = useQuery({ queryKey: ['config'], queryFn: api.config })
  const startScan = useMutation({
    mutationFn: (command: ScanCommand) =>
      command.scanType === 'filesystem'
        ? api.startFilesystem(command.input)
        : api.startTLS(command.input),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['runs'] })
      setScanType(null)
      startTransition(() => navigate(`/${run.scan_type}/${run.id}`))
    },
  })

  function submitScan(input: FilesystemScanInput | TLSScanInput) {
    if (scanType === 'filesystem') {
      startScan.mutate({ scanType, input: input as FilesystemScanInput })
    } else if (scanType === 'tls') {
      startScan.mutate({ scanType, input: input as TLSScanInput })
    }
  }

  const apiHealthy = health.data?.components.api.status === 'healthy'
  const agentHealthy = health.data?.components.agent.status === 'healthy'

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink className="brand" to="/" aria-label="QuantumGenie Discovery home">
            <span className="brand-mark" aria-hidden="true">QG</span>
            <span>
              <strong>QuantumGenie</strong>
              <small>Discovery</small>
            </span>
          </NavLink>
          <nav className="primary-nav" aria-label="Primary navigation">
            <NavLink to="/">Discovery Runs</NavLink>
          </nav>
          <div className="health-cluster" aria-label="Local component health">
            <span title={health.error?.message ?? 'Local API'}>
              <i className={apiHealthy ? 'health-ok' : 'health-down'} /> API
            </span>
            <span title={health.data?.components.agent.message ?? 'Discovery agent'}>
              <i className={agentHealthy ? 'health-ok' : 'health-down'} /> Agent
            </span>
          </div>
          <div className="topbar-actions">
            <button
              className="icon-button"
              type="button"
              onClick={() => setSchedulesOpen(true)}
              aria-label="Manage scan schedules"
              title="Scan schedules"
            >
              <CalendarClock size={18} />
            </button>
            <button className="button button-secondary" type="button" onClick={() => setScanType('tls')}>
              <RadioTower size={16} />
              <span>TLS scan</span>
            </button>
            <button className="button button-primary" type="button" onClick={() => setScanType('filesystem')}>
              <FolderSearch size={16} />
              <span>Filesystem scan</span>
            </button>
          </div>
        </div>
      </header>
      {!agentHealthy && health.data ? (
        <div className="connection-banner" role="status">
          <ShieldCheck size={17} />
          The local API is ready. Start the discovery agent to run live scans.
        </div>
      ) : null}
      <main>
        <Suspense fallback={<LoadingState label="Loading view" />}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/filesystem/:runId" element={<FilesystemReportPage />} />
            <Route path="/tls/:runId" element={<TLSReportPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="app-footer">
        <span>Local-only cryptographic discovery</span>
        <span>Metadata evidence, no payload capture</span>
      </footer>
      {scanType ? (
        <ScanDialog
          open
          key={scanType}
          scanType={scanType}
          config={config.data}
          pending={startScan.isPending}
          error={startScan.error?.message}
          onClose={() => {
            setScanType(null)
            startScan.reset()
          }}
          onSubmit={submitScan}
        />
      ) : null}
      {schedulesOpen ? (
        <SchedulesDialog open config={config.data} onClose={() => setSchedulesOpen(false)} />
      ) : null}
    </div>
  )
}

export default App