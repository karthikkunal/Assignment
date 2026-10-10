import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, Inbox, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { titleCase } from '../lib/format'
import type { RunStatus } from '../lib/types'

export function StatusChip({ status }: { status: RunStatus | string }) {
  return <span className={`status-chip status-${status}`}>{titleCase(status)}</span>
}

export function MetricTile({
  label,
  value,
  detail,
  icon: Icon,
  tone = 'neutral',
}: {
  label: string
  value: ReactNode
  detail?: ReactNode
  icon: LucideIcon
  tone?: 'neutral' | 'green' | 'amber' | 'coral' | 'teal'
}) {
  return (
    <article className={`metric-tile metric-${tone}`}>
      <div className="metric-icon" aria-hidden="true">
        <Icon size={18} strokeWidth={1.8} />
      </div>
      <div>
        <p className="metric-label">{label}</p>
        <p className="metric-value">{value}</p>
        {detail ? <p className="metric-detail">{detail}</p> : null}
      </div>
    </article>
  )
}

export function SectionHeading({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  )
}

export function LoadingState({ label = 'Loading evidence' }: { label?: string }) {
  return (
    <div className="state-panel" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>{label}</p>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-panel state-error" role="alert">
      <AlertTriangle size={24} />
      <div>
        <strong>Unable to load evidence</strong>
        <p>{message}</p>
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  message,
}: {
  title: string
  message: string
}) {
  return (
    <div className="state-panel">
      <Inbox size={25} />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  )
}