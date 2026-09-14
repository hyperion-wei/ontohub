import React, { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, Simulation, SimulationNodeDatum } from 'd3-force'
import { select } from 'd3-selection'
import { zoom as d3zoom, zoomIdentity, D3ZoomEvent, ZoomBehavior, ZoomTransform } from 'd3-zoom'

const WIDTH = 900
const HEIGHT = 600
const MIN_SCALE = 0.3
const MAX_SCALE = 3

interface GraphNode extends SimulationNodeDatum {
  id: string
  label: string
  type: string
  properties: Record<string, unknown>
}

interface GraphEdge {
  source: string | GraphNode
  target: string | GraphNode
  label: string
}

interface GraphData {
  nodes: { id: string; label: string; type: string; properties: Record<string, unknown> }[]
  edges: { source: string; target: string; label: string }[]
  nodeCount: number
  edgeCount: number
}

interface HoverInfo {
  node: GraphNode
  x: number
  y: number
}

const TYPE_COLORS: Record<string, { fill: string; stroke: string }> = {
  Provider: { fill: '#dbeafe', stroke: '#2563eb' },
  Model: { fill: '#dcfce7', stroke: '#16a34a' },
  ApiKey: { fill: '#fef3c7', stroke: '#d97706' },
  BaseURL: { fill: '#f3e8ff', stroke: '#9333ea' },
  Monitor: { fill: '#fce7f3', stroke: '#ec4899' },
  MonitorGroup: { fill: '#e0e7ff', stroke: '#6366f1' },
  HealthCheck: { fill: '#fef9c3', stroke: '#ca8a04' },
  MonitorTemplate: { fill: '#ccfbf1', stroke: '#0d9488' },
  KeyModelMapping: { fill: '#fee2e2', stroke: '#dc2626' },
}

const DEFAULT_COLOR = { fill: '#f1f5f9', stroke: '#94a3b8' }

export function GraphPanel() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [renderLinks, setRenderLinks] = useState<GraphEdge[]>([])
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const [filter, setFilter] = useState('')
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const simulationRef = useRef<Simulation<GraphNode, GraphEdge> | null>(null)
  const draggingRef = useRef<GraphNode | null>(null)

  useEffect(() => {
    fetch('/api/graph')
      .then(r => {
        if (!r.ok) throw new Error('bad status')
        return r.json()
      })
      .then((data: GraphData) => {
        setGraphData(data)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!graphData) return
    setHover(null)

    const filteredNodes = filter
      ? graphData.nodes.filter(n => n.type.toLowerCase().includes(filter.toLowerCase()) || n.label.toLowerCase().includes(filter.toLowerCase()))
      : graphData.nodes

    const nodeIds = new Set(filteredNodes.map(n => n.id))
    const filteredEdges = graphData.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

    const simNodes: GraphNode[] = filteredNodes.map(n => ({
      id: n.id,
      label: n.label,
      type: n.type,
      properties: n.properties,
    }))
    const simLinks: GraphEdge[] = filteredEdges.map(e => ({
      source: e.source,
      target: e.target,
      label: e.label,
    }))

    const sim = forceSimulation<GraphNode>(simNodes)
      .force('link', forceLink<GraphNode, GraphEdge>(simLinks).id(d => d.id).distance(120))
      .force('charge', forceManyBody().strength(-280))
      .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
      .force('collide', forceCollide(40))
      .on('tick', () => {
        setNodes([...simNodes])
        setRenderLinks([...simLinks])
      })

    simulationRef.current = sim
    return () => { sim.stop() }
  }, [graphData, filter])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const zoomBehavior = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([MIN_SCALE, MAX_SCALE])
      .filter((event: any) => {
        if (event.type === 'wheel') return true
        if (event.target?.closest?.('[data-graph-node]')) return false
        return !event.ctrlKey && !event.button
      })
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => setTransform(event.transform))
    zoomBehaviorRef.current = zoomBehavior
    select(svg).call(zoomBehavior)
    return () => { select(svg).on('.zoom', null) }
  }, [graphData])

  const zoomBy = (factor: number) => {
    const svg = svgRef.current
    const zb = zoomBehaviorRef.current
    if (!svg || !zb) return
    select(svg).call(zb.scaleBy, factor)
  }

  const resetZoom = () => {
    const svg = svgRef.current
    const zb = zoomBehaviorRef.current
    if (!svg || !zb) return
    select(svg).call(zb.transform, zoomIdentity)
  }

  const toSvgPoint = (clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    const vx = ((clientX - rect.left) / rect.width) * WIDTH
    const vy = ((clientY - rect.top) / rect.height) * HEIGHT
    return { x: (vx - transform.x) / transform.k, y: (vy - transform.y) / transform.k }
  }

  const handlePointerDown = (node: GraphNode, e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture(e.pointerId)
    draggingRef.current = node
    simulationRef.current?.alphaTarget(0.3).restart()
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    const node = draggingRef.current
    if (!node) return
    const { x, y } = toSvgPoint(e.clientX, e.clientY)
    node.fx = x
    node.fy = y
  }

  const handlePointerUp = () => {
    draggingRef.current = null
    simulationRef.current?.alphaTarget(0)
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载图数据中...</div>
  }
  if (error) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">图数据加载失败，请确认后端服务已启动</div>
  }

  const typeSet = [...new Set((graphData?.nodes || []).map(n => n.type))]

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-gray-50 flex-shrink-0">
        <input
          type="text"
          placeholder="筛选节点..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="text-xs border rounded px-2 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <div className="flex items-center gap-2 flex-wrap">
          {typeSet.map(t => {
            const color = TYPE_COLORS[t] || DEFAULT_COLOR
            return (
              <span key={t} className="flex items-center gap-1 text-xs text-gray-500">
                <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color.fill, borderColor: color.stroke, borderWidth: 2 }} />
                {t}
              </span>
            )
          })}
        </div>
        <span className="text-xs text-gray-400 ml-auto">
          {graphData?.nodeCount || 0} 节点 · {graphData?.edgeCount || 0} 边
        </span>
      </div>

      {/* Graph */}
      <div className="flex-1 relative overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full h-full"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <defs>
            <marker id="hub-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
            </marker>
          </defs>
          <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
            {renderLinks.map((link, i) => {
              const source = link.source as GraphNode
              const target = link.target as GraphNode
              if (typeof source === 'string' || typeof target === 'string') return null
              if (source.x == null || source.y == null || target.x == null || target.y == null) return null
              return (
                <g key={i}>
                  <line
                    x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                    stroke="#cbd5e1" strokeWidth={1.5}
                    markerEnd="url(#hub-arrow)"
                    opacity={0.6}
                  />
                  <text
                    x={(source.x + target.x) / 2}
                    y={(source.y + target.y) / 2}
                    className="fill-gray-400 text-[8px]"
                    textAnchor="middle"
                  >
                    {link.label}
                  </text>
                </g>
              )
            })}
            {nodes.map(node => {
              const color = TYPE_COLORS[node.type] || DEFAULT_COLOR
              return (
                <g
                  key={node.id}
                  data-graph-node="true"
                  transform={`translate(${node.x || 0}, ${node.y || 0})`}
                  onPointerDown={e => handlePointerDown(node, e)}
                  onMouseEnter={() => setHover({ node, x: node.x || 0, y: node.y || 0 })}
                  onMouseLeave={() => setHover(null)}
                  className="cursor-move"
                >
                  <circle r={24} fill={color.fill} stroke={color.stroke} strokeWidth={2} />
                  <text textAnchor="middle" dy="0.35em" className="fill-gray-700 text-[9px] font-medium select-none">
                    {node.label.length > 10 ? node.label.slice(0, 10) + '...' : node.label}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>

        {/* Hover tooltip */}
        {hover && (
          <div
            className="absolute z-10 bg-white border rounded-lg shadow-lg p-3 text-xs max-w-xs pointer-events-none"
            style={{
              left: `${((hover.x * transform.k + transform.x) / WIDTH) * 100}%`,
              top: `${((hover.y * transform.k + transform.y) / HEIGHT) * 100}%`,
            }}
          >
            <div className="font-semibold text-gray-700 mb-1">{hover.node.label}</div>
            <div className="text-gray-400 mb-1">{hover.node.type} · {hover.node.id}</div>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {Object.entries(hover.node.properties).slice(0, 8).map(([k, v]) => (
                <div key={k} className="text-gray-600">
                  <span className="font-medium">{k}</span>
                  <span className="text-gray-400">: {String(v).slice(0, 40)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Zoom controls */}
        <div className="absolute bottom-3 right-3 flex flex-col gap-1 z-10">
          <button onClick={() => zoomBy(1.2)} className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50" title="放大">+</button>
          <button onClick={() => zoomBy(1 / 1.2)} className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50" title="缩小">-</button>
          <button onClick={resetZoom} className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50 text-[11px]" title="重置视图">R</button>
        </div>
      </div>
    </div>
  )
}
