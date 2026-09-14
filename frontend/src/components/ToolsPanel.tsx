import React, { useEffect, useState } from 'react'

interface Tool {
  name: string
  description: string
  inputSchema: {
    type: string
    properties: Record<string, { type: string; description?: string; enum?: string[] }>
    required?: string[]
  }
}

interface Props {
  role: string
}

export function ToolsPanel({ role }: Props) {
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [callArgs, setCallArgs] = useState('{}')
  const [callResult, setCallResult] = useState<string | null>(null)
  const [calling, setCalling] = useState(false)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    fetch(`/api/tools?role=${role}`)
      .then(r => r.json())
      .then(data => {
        setTools(data.tools || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [role])

  const filteredTools = filter
    ? tools.filter(t => t.name.toLowerCase().includes(filter.toLowerCase()) || t.description.toLowerCase().includes(filter.toLowerCase()))
    : tools

  const handleCall = async () => {
    if (!selectedTool) return
    setCalling(true)
    setCallResult(null)
    try {
      const args = JSON.parse(callArgs)
      const res = await fetch('/api/tools/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: selectedTool.name, arguments: args, role }),
      })
      const data = await res.json()
      setCallResult(JSON.stringify(data, null, 2))
    } catch (e) {
      setCallResult(`Error: ${e}`)
    } finally {
      setCalling(false)
    }
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载工具列表中...</div>
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* Tool list */}
      <div className="w-80 border-r bg-white flex flex-col flex-shrink-0">
        <div className="px-3 py-2 border-b">
          <input
            type="text"
            placeholder="搜索工具..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full text-xs border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {filteredTools.map(t => (
            <button
              key={t.name}
              onClick={() => { setSelectedTool(t); setCallResult(null) }}
              className={`w-full text-left px-4 py-2.5 border-b border-gray-50 transition-colors ${
                selectedTool?.name === t.name
                  ? 'bg-blue-50 border-l-2 border-l-blue-500'
                  : 'hover:bg-gray-50 border-l-2 border-l-transparent'
              }`}
            >
              <div className={`text-xs font-medium ${selectedTool?.name === t.name ? 'text-blue-700' : 'text-gray-700'}`}>
                {t.name}
              </div>
              <div className="text-xs text-gray-400 mt-0.5 truncate">{t.description}</div>
            </button>
          ))}
        </div>
        <div className="px-3 py-2 border-t text-xs text-gray-400">
          {filteredTools.length} / {tools.length} 工具 · 角色: {role}
        </div>
      </div>

      {/* Tool detail + call */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedTool ? (
          <>
            <div className="px-6 py-4 border-b bg-white">
              <h2 className="text-sm font-semibold text-gray-800">{selectedTool.name}</h2>
              <p className="text-xs text-gray-500 mt-1">{selectedTool.description}</p>
              {Object.keys(selectedTool.inputSchema?.properties || {}).length > 0 && (
                <div className="mt-3">
                  <h3 className="text-xs font-semibold text-gray-500 mb-1">参数:</h3>
                  <div className="space-y-1">
                    {Object.entries(selectedTool.inputSchema.properties).map(([name, prop]) => (
                      <div key={name} className="text-xs text-gray-600">
                        <span className="font-medium">{name}</span>
                        <span className="text-gray-400"> ({prop.type})</span>
                        {selectedTool.inputSchema.required?.includes(name) && (
                          <span className="text-red-400 ml-1">*必填</span>
                        )}
                        {prop.description && <span className="text-gray-400"> — {prop.description}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex-1 flex overflow-hidden">
              {/* Call input */}
              <div className="w-1/2 flex flex-col border-r">
                <div className="px-4 py-2 bg-gray-50 border-b text-xs font-medium text-gray-500">
                  调用参数 (JSON)
                </div>
                <textarea
                  value={callArgs}
                  onChange={e => setCallArgs(e.target.value)}
                  className="flex-1 p-4 text-xs font-mono resize-none focus:outline-none"
                  placeholder='{"key": "value"}'
                />
                <div className="px-4 py-2 border-t">
                  <button
                    onClick={handleCall}
                    disabled={calling}
                    className="px-4 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {calling ? '调用中...' : '调用工具'}
                  </button>
                </div>
              </div>

              {/* Call result */}
              <div className="w-1/2 flex flex-col">
                <div className="px-4 py-2 bg-gray-50 border-b text-xs font-medium text-gray-500">
                  返回结果
                </div>
                <pre className="flex-1 p-4 text-xs font-mono overflow-auto bg-gray-50">
                  {callResult || '点击"调用工具"查看结果'}
                </pre>
              </div>
            </div>
          </>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm">
            选择左侧的工具查看详情和调用
          </div>
        )}
      </div>
    </div>
  )
}
