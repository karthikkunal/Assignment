import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Pause, Play, Plus, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import { formatDate, titleCase } from '../lib/format'
import type { AppConfig, ScanType, ScheduleInput } from '../lib/types'
import { EmptyState, LoadingState } from './ui'

export function SchedulesDialog({
  open,
  config,
  onClose,
}: {
  open: boolean
  config?: AppConfig
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [scanType, setScanType] = useState<ScanType>('filesystem')
  const [interval, setInterval] = useState(60)
  const [roots, setRoots] = useState(() => (config?.default_scan_roots ?? []).join('\n'))
  const [targets, setTargets] = useState(() => (config?.default_probe_targets ?? []).join('\n'))
  const [duration, setDuration] = useState(() => config?.default_tls_duration_seconds ?? 15)

  const schedules = useQuery({
    queryKey: ['schedules'],
    queryFn: api.schedules,
    enabled: open,
  })
  const createSchedule = useMutation({
    mutationFn: api.createSchedule,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['schedules'] })
      setName('')
    },
  })
  const toggleSchedule = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.toggleSchedule(id, enabled),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })
  const deleteSchedule = useMutation({
    mutationFn: api.deleteSchedule,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })

  if (!open) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    const input: ScheduleInput = {
      name,
      scan_type: scanType,
      interval_minutes: interval,
      enabled: true,
    }
    if (scanType === 'filesystem') {
      input.filesystem = { roots: splitLines(roots) }
    } else {
      input.tls = { duration_seconds: duration, probe_targets: splitLines(targets) }
    }
    createSchedule.mutate(input)
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="modal modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="schedule-dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div className="modal-title">
            <span className="modal-icon" aria-hidden="true">
              <CalendarClock size={20} />
            </span>
            <div>
              <p className="eyebrow">Periodic discovery</p>
              <h2 id="schedule-dialog-title">Scan schedules</h2>
            </div>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close" title="Close">
            <X size={19} />
          </button>
        </header>
        <div className="modal-body schedule-layout">
          <form className="schedule-form form-stack" onSubmit={submit}>
            <h3>New schedule</h3>
            <label>
              <span>Name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={80} />
            </label>
            <div className="segmented" aria-label="Scan type">
              <button
                type="button"
                className={scanType === 'filesystem' ? 'active' : ''}
                onClick={() => setScanType('filesystem')}
              >
                Filesystem
              </button>
              <button
                type="button"
                className={scanType === 'tls' ? 'active' : ''}
                onClick={() => setScanType('tls')}
              >
                TLS metadata
              </button>
            </div>
            <label>
              <span>Interval in minutes</span>
              <input
                type="number"
                min={1}
                max={10080}
                value={interval}
                onChange={(event) => setInterval(Number(event.target.value))}
              />
            </label>
            {scanType === 'filesystem' ? (
              <label>
                <span>Filesystem roots</span>
                <textarea value={roots} onChange={(event) => setRoots(event.target.value)} rows={4} />
              </label>
            ) : (
              <>
                <label>
                  <span>Probe targets</span>
                  <textarea value={targets} onChange={(event) => setTargets(event.target.value)} rows={3} />
                </label>
                <label>
                  <span>Duration in seconds</span>
                  <input
                    type="number"
                    min={1}
                    max={300}
                    value={duration}
                    onChange={(event) => setDuration(Number(event.target.value))}
                  />
                </label>
              </>
            )}
            {createSchedule.error ? (
              <p className="form-error">{createSchedule.error.message}</p>
            ) : null}
            <button className="button button-primary" type="submit" disabled={createSchedule.isPending}>
              <Plus size={16} />
              {createSchedule.isPending ? 'Creating...' : 'Create schedule'}
            </button>
          </form>
          <div className="schedule-list">
            <h3>Configured schedules</h3>
            {schedules.isLoading ? <LoadingState label="Loading schedules" /> : null}
            {schedules.data?.length === 0 ? (
              <EmptyState title="No schedules" message="Periodic scans will appear here." />
            ) : null}
            {schedules.data?.map((schedule) => (
              <article className="schedule-row" key={schedule.id}>
                <div>
                  <div className="schedule-row-title">
                    <strong>{schedule.name}</strong>
                    <span className={`status-chip ${schedule.enabled ? 'status-completed' : 'status-queued'}`}>
                      {schedule.enabled ? 'Active' : 'Paused'}
                    </span>
                  </div>
                  <p>
                    {titleCase(schedule.scan_type)} every {schedule.interval_minutes} minutes
                  </p>
                  <small>Next: {formatDate(schedule.next_run_at)}</small>
                </div>
                <div className="row-actions">
                  <button
                    className="icon-button"
                    type="button"
                    title={schedule.enabled ? 'Pause schedule' : 'Resume schedule'}
                    aria-label={schedule.enabled ? 'Pause schedule' : 'Resume schedule'}
                    onClick={() =>
                      toggleSchedule.mutate({ id: schedule.id, enabled: !schedule.enabled })
                    }
                  >
                    {schedule.enabled ? <Pause size={17} /> : <Play size={17} />}
                  </button>
                  <button
                    className="icon-button danger"
                    type="button"
                    title="Delete schedule"
                    aria-label="Delete schedule"
                    onClick={() => deleteSchedule.mutate(schedule.id)}
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n;]/)
    .map((item) => item.trim())
    .filter(Boolean)
}