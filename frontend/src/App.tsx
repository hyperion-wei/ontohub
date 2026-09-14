import React, { useState, useEffect } from 'react'
import { Sidebar, ViewType } from './components/Sidebar'
import { GraphPanel } from './components/GraphPanel'
import { SchemaPanel } from './components/SchemaPanel'
import { ToolsPanel } from './components/ToolsPanel'
import { InstancesPanel } from './components/InstancesPanel'

interface SchemaInfo {
  typeCount: number
  functionCount: number
  actionCount: number
}

export default function App() {
  const [activeView, setActiveView] = useState<ViewType>('graph')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [schemaInfo, setSchemaInfo] = useState<SchemaInfo | null>(null)
  const [role, setRole] = useState('admin')

  useEffect(() => {
    fetch('/api/schema')
      .then(r => r.json())
      .then(data => setSchemaInfo(data))
      .catch(() => {})
  }, [])

  return (
    <div className="h-screen flex bg-gray-50 text-gray-800">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-2 border-b bg-white">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-gray-700">Ontology Hub</span>
            <span className="text-gray-300">|</span>
            {schemaInfo && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-md">
                {schemaInfo.typeCount} 类型 · {schemaInfo.functionCount} 函数 · {schemaInfo.actionCount} 操作
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={role}
              onChange={e => setRole(e.target.value)}
              className="text-xs border rounded px-2 py-1 text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-400"
              title="切换角色"
            >
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeView === 'graph' && <GraphPanel />}
          {activeView === 'schema' && <SchemaPanel />}
          {activeView === 'instances' && <InstancesPanel />}
          {activeView === 'tools' && <ToolsPanel role={role} />}
        </div>
      </div>
    </div>
  )
}
