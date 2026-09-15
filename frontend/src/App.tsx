import React, { useState, useEffect, createContext, useContext } from 'react'
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

interface Workspace {
  name: string
  description: string
  created_at: string
  updated_at: string
}

interface Tool {
  name: string
  description: string
}

// Workspace Context
interface WorkspaceContextType {
  currentWorkspace: string
  refreshKey: number
  switchWorkspace: (name: string) => void
}

const WorkspaceContext = createContext<WorkspaceContextType>({
  currentWorkspace: 'default',
  refreshKey: 0,
  switchWorkspace: () => {},
})

export const useWorkspace = () => useContext(WorkspaceContext)

export default function App() {
  const [activeView, setActiveView] = useState<ViewType>('graph')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [schemaInfo, setSchemaInfo] = useState<SchemaInfo | null>(null)
  const [role, setRole] = useState('admin')
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [currentWorkspace, setCurrentWorkspace] = useState('default')
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState('')
  const [newWorkspaceDesc, setNewWorkspaceDesc] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  // 加载 workspace 列表
  const loadWorkspaces = () => {
    fetch('/api/workspaces')
      .then(r => r.json())
      .then(data => {
        setWorkspaces(data.workspaces || [])
        setCurrentWorkspace(data.current || 'default')
      })
      .catch(() => {})
  }

  // 加载 schema 信息
  const loadSchema = () => {
    fetch('/api/schema')
      .then(r => r.json())
      .then(data => setSchemaInfo(data))
      .catch(() => {})
  }

  useEffect(() => {
    loadWorkspaces()
    loadSchema()
  }, [])

  // 切换 workspace
  const handleSwitchWorkspace = (name: string) => {
    fetch('/api/workspaces/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'switched') {
          setCurrentWorkspace(name)
          setRefreshKey(k => k + 1) // 触发子组件刷新
          loadSchema()
        }
      })
      .catch(() => {})
  }

  // 创建 workspace
  const handleCreateWorkspace = () => {
    if (!newWorkspaceName.trim()) return
    fetch('/api/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newWorkspaceName, description: newWorkspaceDesc }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'created') {
          loadWorkspaces()
          setShowWorkspaceModal(false)
          setNewWorkspaceName('')
          setNewWorkspaceDesc('')
        }
      })
      .catch(() => {})
  }

  // 删除 workspace
  const handleDeleteWorkspace = (name: string) => {
    if (!confirm(`确定要删除工作空间 "${name}" 吗？此操作将删除该空间的所有数据！`)) return
    fetch(`/api/workspaces/${name}`, { method: 'DELETE' })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'deleted') {
          loadWorkspaces()
          if (currentWorkspace === name) {
            handleSwitchWorkspace('default')
          }
        }
      })
      .catch(() => {})
  }

  const workspaceContextValue = {
    currentWorkspace,
    refreshKey,
    switchWorkspace: handleSwitchWorkspace,
  }

  return (
    <WorkspaceContext.Provider value={workspaceContextValue}>
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
              {/* Workspace 选择器 */}
              <div className="flex items-center gap-2">
                <select
                  value={currentWorkspace}
                  onChange={e => handleSwitchWorkspace(e.target.value)}
                  className="text-xs border rounded px-2 py-1 text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-400 bg-blue-50"
                  title="切换工作空间"
                >
                  {workspaces.map(ws => (
                    <option key={ws.name} value={ws.name}>
                      {ws.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setShowWorkspaceModal(true)}
                  className="text-xs text-blue-600 hover:text-blue-800 px-1"
                  title="管理工作空间"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </button>
              </div>
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
            {activeView === 'graph' && <GraphPanel key={`graph-${refreshKey}`} />}
            {activeView === 'schema' && <SchemaPanel key={`schema-${refreshKey}`} />}
            {activeView === 'instances' && <InstancesPanel key={`instances-${refreshKey}`} />}
            {activeView === 'tools' && <ToolsPanel role={role} />}
          </div>
        </div>

        {/* Workspace 管理模态框 */}
        {showWorkspaceModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-96 max-h-[80vh] overflow-hidden">
              <div className="px-4 py-3 border-b flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">工作空间管理</h3>
                <button
                  onClick={() => setShowWorkspaceModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              <div className="p-4 space-y-4">
                {/* 创建新 workspace */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-600">新建工作空间</label>
                  <input
                    type="text"
                    value={newWorkspaceName}
                    onChange={e => setNewWorkspaceName(e.target.value)}
                    placeholder="名称"
                    className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                  />
                  <input
                    type="text"
                    value={newWorkspaceDesc}
                    onChange={e => setNewWorkspaceDesc(e.target.value)}
                    placeholder="描述（可选）"
                    className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                  />
                  <button
                    onClick={handleCreateWorkspace}
                    className="w-full text-sm bg-blue-600 text-white rounded px-3 py-2 hover:bg-blue-700 transition-colors"
                  >
                    创建
                  </button>
                </div>

                {/* 现有 workspace 列表 */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-600">现有工作空间</label>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {workspaces.map(ws => (
                      <div
                        key={ws.name}
                        className={`flex items-center justify-between px-3 py-2 rounded text-sm ${
                          ws.name === currentWorkspace ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'
                        }`}
                      >
                        <div>
                          <span className="font-medium">{ws.name}</span>
                          {ws.description && (
                            <span className="text-xs text-gray-500 ml-2">{ws.description}</span>
                          )}
                        </div>
                        {ws.name !== 'default' && (
                          <button
                            onClick={() => handleDeleteWorkspace(ws.name)}
                            className="text-red-500 hover:text-red-700 text-xs"
                          >
                            删除
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </WorkspaceContext.Provider>
  )
}
