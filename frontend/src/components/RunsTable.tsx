import { Search } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { formatDate, formatDuration, formatNumber, titleCase } from '../lib/format'
import type { DiscoveryRun, RunStatus, ScanType } from '../lib/types'
import { EmptyState, StatusChip } from './ui'

export function RunsTable({
  runs,
  onSelect,
}: {
  runs: DiscoveryRun[]
  onSelect: (run: DiscoveryRun) => void
}) {
  const [search, setSearch] = useState('')
  const [scanType, setScanType] = useState<ScanType | 'all'>('all')
  const [status, setStatus] = useState<RunStatus | 'all'>('all')
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())

  const filtered = runs.filter((run) => {
    if (scanType !== 'all' && run.scan_type !== scanType) return false
    if (status !== 'all' && run.status !== status) return false
    if (!deferredSearch) return true
    return [run.id, run.scan_type, run.trigger_type, run.error_summary]
      .join(' ')
      .toLowerCase()
      .includes(deferredSearch)
  })

  return (
    <div>
      <div className="table-tools">
        <label className="search-field">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search runs"
            aria-label="Search discovery runs"
          />
        </label>
        <select value={scanType} onChange={(event) => setScanType(event.target.value as ScanType | 'all')}>
          <option value="all">All types</option>
          <option value="filesystem">Filesystem</option>
          <option value="tls">TLS metadata</option>
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value as RunStatus | 'all')}>
          <option value="all">All statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      {filtered.length === 0 ? (
        <EmptyState title="No matching runs" message="Change the filters or start a new discovery scan." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Type</th>
                <th>Trigger</th>
                <th>Started</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Records</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr key={run.id}>
                  <td>
                    <button className="table-link mono" type="button" onClick={() => onSelect(run)}>
                      {run.id.slice(0, 10)}
                    </button>
                  </td>
                  <td>{run.scan_type === 'tls' ? 'TLS metadata' : 'Filesystem'}</td>
                  <td>{titleCase(run.trigger_type)}</td>
                  <td>{formatDate(run.started_at ?? run.created_at)}</td>
                  <td>
                    <StatusChip status={run.status} />
                  </td>
                  <td>{formatDuration(run.duration_ms)}</td>
                  <td>{formatNumber(run.record_count)}</td>
                  <td title={run.error_summary}>{formatNumber(run.error_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}