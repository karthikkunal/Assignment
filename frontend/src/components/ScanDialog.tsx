import { FolderSearch, Play, RadioTower, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { AppConfig, FilesystemScanInput, ScanType, TLSScanInput } from '../lib/types'

export function ScanDialog({
  open,
  scanType,
  config,
  pending,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean
  scanType: ScanType
  config?: AppConfig
  pending: boolean
  error?: string
  onClose: () => void
  onSubmit: (input: FilesystemScanInput | TLSScanInput) => void
}) {
  const [roots, setRoots] = useState(() => (config?.default_scan_roots ?? []).join('\n'))
  const [targets, setTargets] = useState(() => (config?.default_probe_targets ?? []).join('\n'))
  const [duration, setDuration] = useState(() => config?.default_tls_duration_seconds ?? 15)

  if (!open) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (scanType === 'filesystem') {
      onSubmit({ roots: splitLines(roots) })
      return
    }
    onSubmit({ duration_seconds: duration, probe_targets: splitLines(targets) })
  }

  const Icon = scanType === 'filesystem' ? FolderSearch : RadioTower
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scan-dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div className="modal-title">
            <span className="modal-icon" aria-hidden="true">
              <Icon size={20} />
            </span>
            <div>
              <p className="eyebrow">Manual discovery</p>
              <h2 id="scan-dialog-title">
                {scanType === 'filesystem' ? 'Run filesystem scan' : 'Run TLS metadata scan'}
              </h2>
            </div>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close" title="Close">
            <X size={19} />
          </button>
        </header>
        <form onSubmit={submit}>
          <div className="modal-body form-stack">
            {scanType === 'filesystem' ? (
              <label>
                <span>Filesystem roots</span>
                <textarea
                  value={roots}
                  onChange={(event) => setRoots(event.target.value)}
                  rows={6}
                  placeholder={'C:\\ProgramData\\certificates\nC:\\Users\\Public\\certs'}
                />
              </label>
            ) : (
              <>
                <label>
                  <span>Probe targets</span>
                  <textarea
                    value={targets}
                    onChange={(event) => setTargets(event.target.value)}
                    rows={5}
                    placeholder={'example.com:443\ninternal-service.local:8443'}
                  />
                </label>
                <label>
                  <span>Observation duration</span>
                  <div className="range-control">
                    <input
                      type="range"
                      min={1}
                      max={120}
                      value={duration}
                      onChange={(event) => setDuration(Number(event.target.value))}
                    />
                    <input
                      className="number-input"
                      type="number"
                      min={1}
                      max={300}
                      value={duration}
                      onChange={(event) => setDuration(Number(event.target.value))}
                      aria-label="Duration in seconds"
                    />
                    <span>seconds</span>
                  </div>
                </label>
              </>
            )}
            {error ? <p className="form-error">{error}</p> : null}
          </div>
          <footer className="modal-footer">
            <button className="button button-ghost" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="button button-primary" type="submit" disabled={pending}>
              <Play size={16} fill="currentColor" />
              {pending ? 'Starting...' : 'Start scan'}
            </button>
          </footer>
        </form>
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