import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { EvidenceGraph } from '../lib/types'
import { EmptyState } from './ui'

const nodeColors: Record<string, string> = {
  host: '#315f53',
  process: '#3e7ca8',
  certificate: '#e1a72b',
  endpoint: '#dc6b4a',
  service: '#7b6ca8',
}

export function RelationshipGraph({ graph }: { graph: EvidenceGraph }) {
  if (!graph.nodes.length) {
    return (
      <EmptyState
        title="No relationships mapped"
        message="Relationship evidence appears after the agent submits parsed observations."
      />
    )
  }

  const radius = Math.max(180, graph.nodes.length * 18)
  const nodes: Node[] = graph.nodes.map((node, index) => {
    const angle = (index / graph.nodes.length) * Math.PI * 2 - Math.PI / 2
    return {
      id: node.id,
      position: {
        x: 320 + Math.cos(angle) * radius,
        y: 230 + Math.sin(angle) * radius,
      },
      data: { label: node.label },
      style: {
        background: nodeColors[node.type] ?? '#51605b',
        color: '#fff',
        border: '1px solid rgba(0, 0, 0, 0.18)',
        borderRadius: 5,
        fontSize: 11,
        lineHeight: 1.25,
        width: 158,
        padding: 10,
      },
    }
  })
  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: `${edge.type.replaceAll('_', ' ')} x${edge.weight}`,
    type: 'smoothstep',
    animated: edge.type === 'communicates_with',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#71817b' },
    style: { stroke: '#71817b', strokeWidth: Math.min(1 + Math.log2(edge.weight + 1), 4) },
    labelStyle: { fill: '#3f4b47', fontSize: 10 },
    labelBgStyle: { fill: '#f8faf8', fillOpacity: 0.92 },
  }))

  return (
    <div>
      <div className="graph-legend" aria-label="Relationship node types">
        {Object.entries(nodeColors).map(([type, color]) => (
          <span key={type}>
            <i style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
      <div className="relationship-canvas">
        <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.3} maxZoom={1.8}>
          <Background color="#dce4de" gap={22} size={1} />
          <MiniMap
            nodeColor={(node) => String(node.style?.background ?? '#51605b')}
            maskColor="rgba(244, 247, 244, 0.72)"
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  )
}