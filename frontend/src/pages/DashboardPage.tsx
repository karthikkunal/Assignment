import { useQuery } from '@tanstack/react-query'
import { Activity, Database, FolderKey, RefreshCw, RadioTower } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { DistributionDonut, EvidenceTrend } from '../components/Charts'
import { RunsTable } from '../components/RunsTable'
import { ErrorState, LoadingState, MetricTile, SectionHeading } from '../components/ui'
import { api } from '../lib/api'
import { formatNumber } from '../lib/format'
import type { DiscoveryRun } from '../lib/types'

export function DashboardPage() {
  const navigate = useNavigate()
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 3000,
  })
  const runs = useQuery({
    queryKey: ['runs'],
    queryFn: api.runs,
    refetchInterval: 2500,
  })

  function selectRun(run: DiscoveryRun) {
    navigate(`/${run.scan_type}/${run.id}`)
  }

  if (dashboard.isLoading || runs.isLoading) {
    return <LoadingState label="Loading discovery history" />
  }
  if (dashboard.error || runs.error) {
    return <ErrorState message={(dashboard.error ?? runs.error)?.message ?? 'Unknown API error'} />
  }

  const totals = dashboard.data?.totals
  return (
    <div className="page-content page-enter">
      <header className="page-header">
        <div>
          <p className="eyebrow">Local evidence control plane</p>
          <h1>Discovery Runs</h1>
          <p className="page-subtitle">Current state and historical evidence from this endpoint.</p>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={() => {
            void dashboard.refetch()
            void runs.refetch()
          }}
          aria-label="Refresh discovery data"
          title="Refresh"
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <section className="metric-grid" aria-label="Discovery summary">
        <MetricTile
          label="Recorded runs"
          value={formatNumber(totals?.total_runs)}
          detail={`${formatNumber(totals?.active_runs)} active now`}
          icon={Activity}
          tone="green"
        />
        <MetricTile
          label="Evidence records"
          value={formatNumber(totals?.total_evidence)}
          detail="Across all retained runs"
          icon={Database}
          tone="teal"
        />
        <MetricTile
          label="Filesystem runs"
          value={formatNumber(totals?.filesystem_runs)}
          detail="Certificate inventory"
          icon={FolderKey}
          tone="amber"
        />
        <MetricTile
          label="TLS runs"
          value={formatNumber(totals?.tls_runs)}
          detail="Connection metadata"
          icon={RadioTower}
          tone="coral"
        />
      </section>

      <section className="visual-grid visual-grid-dashboard">
        <article className="chart-panel chart-panel-wide">
          <SectionHeading title="Evidence over time" description="Findings and completed scans by day" />
          <EvidenceTrend data={dashboard.data?.trend ?? []} />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Run posture" description="Current status distribution" />
          <DistributionDonut data={dashboard.data?.status_counts ?? []} />
        </article>
      </section>

      <section className="data-section">
        <SectionHeading
          title="Run history"
          description={`${formatNumber(runs.data?.length)} retained runs`}
        />
        <RunsTable runs={runs.data ?? []} onSelect={selectRun} />
      </section>
    </div>
  )
}