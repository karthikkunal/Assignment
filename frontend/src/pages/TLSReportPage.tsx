import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Binary, Cable, KeyRound, Network, Search, ShieldCheck } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DistributionBar, DistributionDonut, EvidenceTrend } from '../components/Charts'
import { RelationshipGraph } from '../components/RelationshipGraph'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricTile,
  SectionHeading,
  StatusChip,
} from '../components/ui'
import { api } from '../lib/api'
import { formatDate, formatNumber, shortFingerprint, titleCase } from '../lib/format'

export function TLSReportPage() {
  const { runId = '' } = useParams()
  const [search, setSearch] = useState('')
  const [version, setVersion] = useState('all')
  const [outcome, setOutcome] = useState('all')
  const deferredSearch = useDeferredValue(search.toLowerCase().trim())
  const report = useQuery({
    queryKey: ['tls-report', runId],
    queryFn: () => api.tlsReport(runId),
    enabled: Boolean(runId),
    refetchInterval: 2500,
  })

  if (report.isLoading) return <LoadingState label="Loading TLS evidence" />
  if (report.error) return <ErrorState message={report.error.message} />
  if (!report.data) return <ErrorState message="The TLS report is unavailable." />

  const { run, summary, distributions, observations, graph } = report.data
  const filtered = observations.filter((observation) => {
    if (version !== 'all' && observation.tls_version !== version) return false
    if (outcome !== 'all' && observation.handshake_outcome !== outcome) return false
    if (!deferredSearch) return true
    return [
      observation.hostname,
      observation.destination_ip,
      observation.process_name,
      observation.cipher_suite,
      observation.peer_certificate_subject,
    ]
      .join(' ')
      .toLowerCase()
      .includes(deferredSearch)
  })

  return (
    <div className="page-content page-enter">
      <header className="report-header">
        <Link className="back-link" to="/">
          <ArrowLeft size={16} /> Discovery Runs
        </Link>
        <div className="report-title-row">
          <div>
            <p className="eyebrow">TLS Metadata Scan Report</p>
            <h1>Connection evidence</h1>
            <p className="page-subtitle mono">Run {run.id}</p>
          </div>
          <div className="report-status">
            <StatusChip status={run.status} />
            <span>{formatDate(run.completed_at ?? run.created_at)}</span>
          </div>
        </div>
      </header>

      <section className="metric-grid" aria-label="TLS metadata summary">
        <MetricTile
          label="Events observed"
          value={formatNumber(summary.events_observed)}
          detail={`${formatNumber(summary.successful_handshakes)} successful handshakes`}
          icon={Cable}
          tone="green"
        />
        <MetricTile
          label="Remote endpoints"
          value={formatNumber(summary.unique_endpoints)}
          detail={`${formatNumber(summary.unique_ports)} unique ports`}
          icon={Network}
          tone="teal"
        />
        <MetricTile
          label="Peer certificates"
          value={formatNumber(summary.certificates_observed)}
          detail="Metadata only"
          icon={ShieldCheck}
          tone="amber"
        />
        <MetricTile
          label="Relationships"
          value={formatNumber(summary.mapped_relationships)}
          detail={`${formatNumber(summary.errors)} evidence errors`}
          icon={Binary}
          tone="coral"
        />
      </section>

      <section className="visual-grid">
        <article className="chart-panel">
          <SectionHeading title="TLS versions" />
          <DistributionDonut data={distributions.tls_versions} />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Cipher suites" />
          <DistributionBar data={distributions.cipher_suites} color="#3e7ca8" />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Top endpoints" />
          <DistributionBar data={distributions.endpoints} color="#dc6b4a" />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Certificate posture" />
          <DistributionDonut data={distributions.certificate_posture} />
        </article>
        <article className="chart-panel chart-panel-full">
          <SectionHeading title="Activity timeline" />
          <EvidenceTrend
            data={distributions.activity.map((point) => ({
              date: point.label.slice(11),
              findings: point.value,
              runs: 0,
            }))}
          />
        </article>
      </section>

      <section className="data-section">
        <SectionHeading
          title="TLS observations"
          description={`${formatNumber(filtered.length)} of ${formatNumber(observations.length)} records`}
        />
        <div className="table-tools">
          <label className="search-field">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Endpoint, process, cipher, certificate"
              aria-label="Search TLS observations"
            />
          </label>
          <select value={version} onChange={(event) => setVersion(event.target.value)}>
            <option value="all">All TLS versions</option>
            {distributions.tls_versions.map((point) => (
              <option value={point.label} key={point.label}>
                {point.label}
              </option>
            ))}
          </select>
          <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
            <option value="all">All outcomes</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="not_visible_in_tcp_table">Not visible</option>
          </select>
        </div>
        {filtered.length === 0 ? (
          <EmptyState title="No matching TLS evidence" message="Change the observation filters." />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Observed</th>
                  <th>Remote endpoint</th>
                  <th>Direction</th>
                  <th>Process</th>
                  <th>Protocol</th>
                  <th>Cipher suite</th>
                  <th>Peer certificate</th>
                  <th>Events</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((observation) => (
                  <tr key={observation.id}>
                    <td>{formatDate(observation.observed_at)}</td>
                    <td className="path-cell">
                      <strong>{observation.hostname || observation.destination_ip || 'Unknown'}</strong>
                      <span>
                        {observation.destination_ip || 'Unresolved'}:{observation.destination_port}
                      </span>
                    </td>
                    <td>{titleCase(observation.direction)}</td>
                    <td title={observation.executable}>
                      {observation.process_name || 'Unavailable'}
                      {observation.pid ? <small>PID {observation.pid}</small> : null}
                    </td>
                    <td>
                      {observation.tls_version || 'Not visible'}
                      <small>{titleCase(observation.handshake_outcome)}</small>
                    </td>
                    <td>{observation.cipher_suite || '-'}</td>
                    <td title={observation.peer_certificate_subject}>
                      <span className="certificate-cell">
                        <KeyRound size={14} />
                        {shortFingerprint(observation.peer_certificate_fingerprint)}
                      </span>
                    </td>
                    <td>{formatNumber(observation.event_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="data-section">
        <SectionHeading
          title="Relationship map"
          description="Process, endpoint, service, and certificate evidence"
        />
        <RelationshipGraph graph={graph} />
      </section>
    </div>
  )
}