import React, { useEffect, useState } from 'react'

interface TypeInfo {
  name: string
  description: string
  propertyCount: number
  linkCount: number
  instanceCount: number
}

export function InstancesPanel() {
  const [types, setTypes] = useState<TypeInfo[]>([])
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [instances, setInstances] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedInstance, setSelectedInstance] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    fetch('/api/tools/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'ontology_list_types', arguments: {}, role: 'admin' }),
    })
      .then(r => r.json())
      .then(data => {
        const result = data.result || []
        setTypes(result)
        if (result.length > 0 && !selectedType) {
          setSelectedType(result[0].name)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedType) return
    setLoading(true)
    fetch('/api/tools/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'ontology_query_instances',
        arguments: { object_type: selectedType },
        role: 'admin',
      }),
    })
      .then(r => r.json())
      .then(data => {
        setInstances(data.result || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [selectedType])

  const columns = instances.length > 0 ? Object.keys(instances[0]).slice(0, 6) : []

  return (
    <div className="h-full flex overflow-hidden">
      {/* Type list */}
      <div className="w-56 border-r bg-white overflow-y-auto flex-shrink-0">
        <div className="px-3 py-2 border-b text-xs font-semibold text-gray-400 uppercase tracking-wider">
          对象类型
        </div>
        {types.map(t => (
          <button
            key={t.name}
            onClick={() => { setSelectedType(t.name); setSelectedInstance(null) }}
            className={`w-full text-left px-4 py-2.5 border-b border-gray-50 transition-colors ${
              selectedType === t.name
                ? 'bg-blue-50 border-l-2 border-l-blue-500'
                : 'hover:bg-gray-50 border-l-2 border-l-transparent'
            }`}
          >
            <div className={`text-xs font-medium ${selectedType === t.name ? 'text-blue-700' : 'text-gray-700'}`}>
              {t.name}
            </div>
            <div className="text-xs text-gray-400 mt-0.5">{t.instanceCount} 实例</div>
          </button>
        ))}
      </div>

      {/* Instance table */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 py-2 border-b bg-gray-50 text-xs text-gray-500 flex-shrink-0">
          {selectedType} · {instances.length} 条记录
        </div>
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载中...</div>
          ) : instances.length === 0 ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">暂无数据</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b">
                  {columns.map(col => (
                    <th key={col} className="text-left px-4 py-2 text-xs font-medium text-gray-500 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {instances.map((inst, i) => (
                  <tr
                    key={i}
                    onClick={() => setSelectedInstance(inst)}
                    className={`border-b border-gray-50 cursor-pointer transition-colors ${
                      selectedInstance === inst ? 'bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    {columns.map(col => (
                      <td key={col} className="px-4 py-2 text-xs text-gray-700 whitespace-nowrap max-w-[200px] truncate">
                        {String(inst[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Instance detail */}
      {selectedInstance && (
        <div className="w-80 border-l bg-white overflow-y-auto flex-shrink-0">
          <div className="px-4 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500 flex items-center justify-between">
            <span>实例详情</span>
            <button onClick={() => setSelectedInstance(null)} className="text-gray-400 hover:text-gray-600">x</button>
          </div>
          <div className="p-4 space-y-2">
            {Object.entries(selectedInstance).map(([key, value]) => (
              <div key={key}>
                <div className="text-xs font-medium text-gray-500">{key}</div>
                <div className="text-xs text-gray-700 mt-0.5 break-all">
                  {typeof value === 'object' ? JSON.stringify(value) : String(value ?? 'null')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
