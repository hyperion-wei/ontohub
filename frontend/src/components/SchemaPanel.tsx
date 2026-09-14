import React, { useEffect, useState } from 'react'

interface TypeInfo {
  name: string
  description: string
  propertyCount: number
  linkCount: number
  instanceCount: number
}

interface SchemaData {
  object_types: Record<string, {
    name: string
    description: string
    properties: Record<string, { type: string; required?: boolean; primary_key?: boolean; description?: string }>
    links: Record<string, { target: string; foreign_key: string }>
  }>
  functions: Record<string, { name: string; description: string; params: Record<string, unknown> }>
  actions: Record<string, { name: string; description: string; params: Record<string, unknown> }>
  typeCount: number
  functionCount: number
  actionCount: number
}

export function SchemaPanel() {
  const [schema, setSchema] = useState<SchemaData | null>(null)
  const [types, setTypes] = useState<TypeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [tab, setTab] = useState<'types' | 'functions' | 'actions'>('types')

  useEffect(() => {
    Promise.all([
      fetch('/api/schema').then(r => r.json()),
    ]).then(([schemaData]) => {
      setSchema(schemaData)
      // Build type list
      const typeList: TypeInfo[] = Object.values(schemaData.object_types || {}).map((t: any) => ({
        name: t.name,
        description: t.description,
        propertyCount: Object.keys(t.properties || {}).length,
        linkCount: Object.keys(t.links || {}).length,
        instanceCount: 0,
      }))
      setTypes(typeList)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载本体结构中...</div>
  }

  const selectedTypeDef = selectedType && schema?.object_types?.[selectedType]

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b bg-white flex-shrink-0">
        {(['types', 'functions', 'actions'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'types' ? `对象类型 (${schema?.typeCount || 0})` :
             t === 'functions' ? `函数 (${schema?.functionCount || 0})` :
             `操作 (${schema?.actionCount || 0})`}
          </button>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left list */}
        <div className="w-64 border-r bg-white overflow-y-auto flex-shrink-0">
          {tab === 'types' && types.map(t => (
            <button
              key={t.name}
              onClick={() => setSelectedType(t.name)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 transition-colors ${
                selectedType === t.name ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50 border-l-2 border-l-transparent'
              }`}
            >
              <div className={`text-sm font-medium ${selectedType === t.name ? 'text-blue-700' : 'text-gray-700'}`}>
                {t.name}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {t.propertyCount} 属性 · {t.linkCount} 关系
              </div>
            </button>
          ))}
          {tab === 'functions' && Object.values(schema?.functions || {}).map((f: any) => (
            <div key={f.name} className="px-4 py-3 border-b border-gray-50">
              <div className="text-sm font-medium text-gray-700">{f.name}</div>
              <div className="text-xs text-gray-400 mt-0.5">{f.description}</div>
            </div>
          ))}
          {tab === 'actions' && Object.values(schema?.actions || {}).map((a: any) => (
            <div key={a.name} className="px-4 py-3 border-b border-gray-50">
              <div className="text-sm font-medium text-gray-700">{a.name}</div>
              <div className="text-xs text-gray-400 mt-0.5">{a.description}</div>
            </div>
          ))}
        </div>

        {/* Right detail */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'types' && selectedTypeDef ? (
            <div>
              <h2 className="text-lg font-semibold text-gray-800 mb-1">{selectedTypeDef.name}</h2>
              <p className="text-sm text-gray-500 mb-4">{selectedTypeDef.description}</p>

              <h3 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wider">属性</h3>
              <div className="bg-white rounded-lg border overflow-hidden mb-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b">
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">字段</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">类型</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">必填</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">主键</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(selectedTypeDef.properties || {}).map(([name, prop]: [string, any]) => (
                      <tr key={name} className="border-b border-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-700">{name}</td>
                        <td className="px-4 py-2 text-gray-500">{prop.type}</td>
                        <td className="px-4 py-2">{prop.required ? <span className="text-red-500">是</span> : <span className="text-gray-400">否</span>}</td>
                        <td className="px-4 py-2">{prop.primary_key ? <span className="text-blue-500">PK</span> : ''}</td>
                        <td className="px-4 py-2 text-gray-400 text-xs">{prop.description || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {Object.keys(selectedTypeDef.links || {}).length > 0 && (
                <>
                  <h3 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wider">关系</h3>
                  <div className="bg-white rounded-lg border overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b">
                          <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">关系名</th>
                          <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">目标类型</th>
                          <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">外键字段</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedTypeDef.links || {}).map(([name, link]: [string, any]) => (
                          <tr key={name} className="border-b border-gray-50">
                            <td className="px-4 py-2 font-medium text-gray-700">{name}</td>
                            <td className="px-4 py-2 text-blue-600">{link.target}</td>
                            <td className="px-4 py-2 text-gray-500">{link.foreign_key}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          ) : tab === 'types' ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              选择左侧的对象类型查看详情
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
