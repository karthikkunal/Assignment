import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatNumber, titleCase } from '../lib/format'
import type { DistributionPoint } from '../lib/types'
import { EmptyState } from './ui'

const palette = ['#147d64', '#e1a72b', '#dc6b4a', '#3e7ca8', '#7b6ca8', '#78936a']

function EvidenceTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value?: number; name?: string; color?: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      {label ? <strong>{titleCase(label)}</strong> : null}
      {payload.map((item) => (
        <p key={`${item.name}-${item.value}`} style={{ color: item.color }}>
          {item.name ? `${titleCase(item.name)}: ` : ''}
          {formatNumber(Number(item.value ?? 0))}
        </p>
      ))}
    </div>
  )
}

export function DistributionBar({
  data,
  color = '#147d64',
}: {
  data: DistributionPoint[]
  color?: string
}) {
  if (!data.length) {
    return <EmptyState title="No distribution yet" message="This run did not produce chartable values." />
  }
  return (
    <div className="chart-canvas">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e4e9e5" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={118}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: '#51605b' }}
            tickFormatter={(value: string) => (value.length > 18 ? `${value.slice(0, 17)}...` : value)}
          />
          <Tooltip content={<EvidenceTooltip />} cursor={{ fill: '#eef3ef' }} />
          <Bar dataKey="value" fill={color} radius={[0, 3, 3, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DistributionDonut({ data }: { data: DistributionPoint[] }) {
  if (!data.length) {
    return <EmptyState title="No distribution yet" message="This run did not produce chartable values." />
  }
  const total = data.reduce((sum, point) => sum + point.value, 0)
  return (
    <div className="donut-layout">
      <div className="chart-canvas chart-donut">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius={52}
              outerRadius={78}
              paddingAngle={2}
              stroke="none"
            >
              {data.map((point, index) => (
                <Cell key={point.label} fill={palette[index % palette.length]} />
              ))}
            </Pie>
            <Tooltip content={<EvidenceTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-total" aria-hidden="true">
          <strong>{formatNumber(total)}</strong>
          <span>Total</span>
        </div>
      </div>
      <ul className="chart-legend">
        {data.map((point, index) => (
          <li key={point.label}>
            <span style={{ backgroundColor: palette[index % palette.length] }} />
            <span title={point.label}>{titleCase(point.label)}</span>
            <strong>{formatNumber(point.value)}</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function EvidenceTrend({
  data,
}: {
  data: Array<{ date: string; findings: number; runs: number }>
}) {
  if (!data.length) {
    return <EmptyState title="No trend yet" message="Complete a scan to start the evidence timeline." />
  }
  return (
    <div className="chart-canvas chart-wide">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 18, bottom: 2, left: -18 }}>
          <CartesianGrid stroke="#e4e9e5" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#51605b' }} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
          <Tooltip content={<EvidenceTooltip />} />
          <Line
            type="monotone"
            dataKey="findings"
            stroke="#147d64"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#147d64', strokeWidth: 0 }}
          />
          <Line
            type="monotone"
            dataKey="runs"
            stroke="#dc6b4a"
            strokeWidth={2}
            dot={{ r: 3, fill: '#dc6b4a', strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}