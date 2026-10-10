import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, BadgeCheck, Copy, FileKey2, Search } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DistributionBar, DistributionDonut } from '../components/Charts'
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

export function FilesystemReportPage() {
  const { runId = '' } = useParams()
  const [search, setSearch] = useState('')
  const [validity, setValidity] = useState('all')
  const [parsing, setParsing] = useState('all')
  const deferredSearch = useDeferredValue(search.toLowerCase().trim())
  const report = useQuery({
    queryKey: ['filesystem-report', runId],
    queryFn: () => api.filesystemReport(runId),
    enabled: Boolean(runId),
    refetchInterval: 2500,
  })

  if (report.isLoading) return <LoadingState label="Loading certificate inventory" />
  if (report.error) return <ErrorState message={report.error.message} />
  if (!report.data) return <ErrorState message="The filesystem report is unavailable." />

  const { run, summary, distributions, observations, graph } = report.data
  const filtered = observations.filter((observation) => {
    if (validity !== 'all' && observation.validity_status !== validity) return false
    if (parsing !== 'all' && observation.parsing_status !== parsing) return false
    if (!deferredSearch) return true
    return [
      observation.path,
      observation.subject,
      observation.issuer,
      observation.fingerprint_sha256,
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
            <p className="eyebrow">File System Scan Report</p>
            <h1>Certificate inventory</h1>
            <p className="page-subtitle mono">Run {run.id}</p>
          </div>
          <div className="report-status">
            <StatusChip status={run.status} />
            <span>{formatDate(run.completed_at ?? run.created_at)}</span>
          </div>
        </div>
      </header>

      {run.status === 'failed' && run.error_summary ? (
        <div className="alert-banner" role="alert">
          <AlertTriangle size={18} /> {run.error_summary}
        </div>
      ) : null}

      <section className="metric-grid" aria-label="Certificate summary">
        <MetricTile
          label="Certificates found"
          value={formatNumber(summary.certificates_found)}
          detail={`${formatNumber(summary.unique_certificates)} unique`}
          icon={FileKey2}
          tone="green"
        />
        <MetricTile
          label="Valid"
          value={formatNumber(summary.valid)}
          detail={`${formatNumber(summary.expiring)} expiring`}
          icon={BadgeCheck}
          tone="teal"
        />
        <MetricTile
          label="Expired"
          value={formatNumber(summary.expired)}
          detail={`${formatNumber(summary.parse_failed)} parse failures`}
          icon={AlertTriangle}
          tone="coral"
        />
        <MetricTile
          label="Duplicate locations"
          value={formatNumber(summary.duplicate_observations)}
          detail="Resolved by fingerprint"
          icon={Copy}
          tone="amber"
        />
      </section>

      <section className="visual-grid">
        <article className="chart-panel">
          <SectionHeading title="Validity posture" />
          <DistributionDonut data={distributions.validity} />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Public-key algorithms" />
          <DistributionBar data={distributions.algorithms} color="#3e7ca8" />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Leading issuers" />
          <DistributionBar data={distributions.issuers} color="#7b6ca8" />
        </article>
        <article className="chart-panel">
          <SectionHeading title="Filesystem locations" />
          <DistributionBar data={distributions.locations} color="#dc6b4a" />
        </article>
      </section>

      <section className="data-section">
        <SectionHeading
          title="Certificate evidence"
          description={`${formatNumber(filtered.length)} of ${formatNumber(observations.length)} observations`}
        />
        <div className="table-tools">
          <label className="search-field">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Path, subject, issuer, fingerprint"
              aria-label="Search certificate evidence"
            />
          </label>
          <select value={validity} onChange={(event) => setValidity(event.target.value)}>
            <option value="all">All validity states</option>
            <option value="valid">Valid</option>
            <option value="expiring">Expiring</option>
            <option value="expired">Expired</option>
            <option value="not_yet_valid">Not yet valid</option>
          </select>
          <select value={parsing} onChange={(event) => setParsing(event.target.value)}>
            <option value="all">All parsing states</option>
            <option value="parsed">Parsed</option>
            <option value="parse_failed">Parse failed</option>
            <option value="access_error">Access error</option>
          </select>
        </div>
        {filtered.length === 0 ? (
          <EmptyState title="No matching certificates" message="Change the inventory filters." />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Subject</th>
                  <th>Issuer</th>
                  <th>Validity</th>
                  <th>Algorithm</th>
                  <th>Signature</th>
                  <th>Fingerprint</th>
                  <th>Parsing</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((observation) => (
                  <tr key={observation.id}>
                    <td className="path-cell" title={observation.path}>
                      <strong>{observation.filename}</strong>
                      <span>{observation.path}</span>
                    </td>
                    <td title={observation.subject}>{observation.subject || 'Unavailable'}</td>
                    <td title={observation.issuer}>{observation.issuer || 'Unavailable'}</td>
                    <td>
                      <span className={`posture posture-${observation.validity_status}`}>
                        {titleCase(observation.validity_status)}
                      </span>
                      <small>{observation.days_to_expiry ?? '-'} days</small>
                    </td>
                    <td>
                      {observation.public_key_algorithm || '-'}
                      {observation.public_key_size ? ` ${observation.public_key_size}` : ''}
                    </td>
                    <td>{observation.signature_algorithm || '-'}</td>
                    <td className="mono" title={observation.fingerprint_sha256}>
                      {shortFingerprint(observation.fingerprint_sha256)}
                    </td>
                    <td title={observation.access_error}>
                      {titleCase(observation.parsing_status)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="data-section">
        <SectionHeading title="Certificate relationships" description="Host and certificate evidence" />
        <RelationshipGraph graph={graph} />
      </section>
    </div>
  )
}