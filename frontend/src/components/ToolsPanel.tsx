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

interface McpToken {
  token: string
  workspace: string
  role: string
  tools: string[]
  toolCount: number
  description: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  configJson?: string
  base_url?: string
}

type ToolType = 'all' | 'admin' | 'function' | 'action'
type PanelTab = 'tools' | 'tokens'

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
  const [toolType, setToolType] = useState<ToolType>('all')
  const [panelTab, setPanelTab] = useState<PanelTab>('tools')
  
  // MCP Token 相关状态
  const [showTokenModal, setShowTokenModal] = useState(false)
  const [tokenWorkspace, setTokenWorkspace] = useState('default')
  const [tokenRole, setTokenRole] = useState('admin')
  const [tokenDesc, setTokenDesc] = useState('')
  const [tokenExpiry, setTokenExpiry] = useState<number | ''>('')
  const [tokenBaseUrl, setTokenBaseUrl] = useState('')
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [useCustomTools, setUseCustomTools] = useState(false)
  const [generatedToken, setGeneratedToken] = useState<McpToken | null>(null)
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [workspaces, setWorkspaces] = useState<string[]>([])
  
  // Token 列表状态
  const [tokens, setTokens] = useState<McpToken[]>([])
  const [loadingTokens, setLoadingTokens] = useState(false)
  const [selectedTokenDetail, setSelectedTokenDetail] = useState<McpToken | null>(null)

  useEffect(() => {
    fetch(`/api/tools?role=${role}`)
      .then(r => r.json())
      .then(data => {
        setTools(data.tools || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))

    // 加载 workspace 列表
    fetch('/api/workspaces')
      .then(r => r.json())
      .then(data => {
        const wsList = (data.workspaces || []).map((w: any) => w.name)
        setWorkspaces(wsList)
        setTokenWorkspace(data.current || 'default')
      })
      .catch(() => {})

    // 加载 Token 列表
    loadTokens()
  }, [role])

  const loadTokens = () => {
    setLoadingTokens(true)
    fetch('/api/mcp/tokens')
      .then(r => r.json())
      .then(data => {
        setTokens(data.tokens || [])
        setLoadingTokens(false)
      })
      .catch(() => setLoadingTokens(false))
  }

  // 按类型筛选工具
  const getToolsByType = (type: ToolType): Tool[] => {
    switch (type) {
      case 'admin':
        return tools.filter(t => t.name.startsWith('ontology_'))
      case 'function':
        return tools.filter(t => t.name.startsWith('function:'))
      case 'action':
        return tools.filter(t => t.name.startsWith('action:'))
      default:
        return tools
    }
  }

  const typeFilteredTools = getToolsByType(toolType)
  const filteredTools = filter
    ? typeFilteredTools.filter(t => t.name.toLowerCase().includes(filter.toLowerCase()) || t.description.toLowerCase().includes(filter.toLowerCase()))
    : typeFilteredTools

  const toolCounts = {
    all: tools.length,
    admin: tools.filter(t => t.name.startsWith('ontology_')).length,
    function: tools.filter(t => t.name.startsWith('function:')).length,
    action: tools.filter(t => t.name.startsWith('action:')).length,
  }

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

  // 生成 MCP Token
  const handleGenerateToken = async () => {
    setGenerating(true)
    try {
      const body: any = {
        workspace: tokenWorkspace,
        role: tokenRole,
        description: tokenDesc,
      }
      if (tokenExpiry) body.expires_in_days = tokenExpiry
      if (tokenBaseUrl) body.base_url = tokenBaseUrl
      if (useCustomTools && selectedTools.length > 0) body.tools = selectedTools

      const res = await fetch('/api/mcp/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      setGeneratedToken(data)
      loadTokens() // 刷新列表
    } catch (e) {
      console.error('Failed to generate token:', e)
    } finally {
      setGenerating(false)
    }
  }

  // 删除 Token
  const handleDeleteToken = async (token: string) => {
    if (!confirm('确定要删除此 Token 吗？')) return
    try {
      await fetch(`/api/mcp/token/${encodeURIComponent(token)}`, { method: 'DELETE' })
      loadTokens()
    } catch (e) {
      console.error('Failed to delete token:', e)
    }
  }

  // 查看 Token 详情
  const handleViewToken = async (token: string) => {
    try {
      const res = await fetch(`/api/mcp/token/${encodeURIComponent(token)}`)
      const data = await res.json()
      setSelectedTokenDetail(data)
    } catch (e) {
      console.error('Failed to get token detail:', e)
    }
  }

  // 复制配置到剪贴板
  const handleCopyConfig = async (configJson: string) => {
    try {
      await navigator.clipboard.writeText(configJson)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('Failed to copy:', e)
    }
  }

  // 复制 Token
  const handleCopyToken = async (token: string) => {
    try {
      await navigator.clipboard.writeText(token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('Failed to copy:', e)
    }
  }

  // 切换工具选择
  const toggleToolSelection = (toolName: string) => {
    setSelectedTools(prev =>
      prev.includes(toolName)
        ? prev.filter(t => t !== toolName)
        : [...prev, toolName]
    )
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载工具列表中...</div>
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 顶部标签页 */}
      <div className="flex border-b bg-white flex-shrink-0">
        <button
          onClick={() => setPanelTab('tools')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            panelTab === 'tools' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          工具列表 ({tools.length})
        </button>
        <button
          onClick={() => setPanelTab('tokens')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            panelTab === 'tokens' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          MCP Token ({tokens.length})
        </button>
      </div>

      {panelTab === 'tools' ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Tool list */}
          <div className="w-80 border-r bg-white flex flex-col flex-shrink-0">
            {/* MCP Token 按钮 */}
            <div className="px-3 py-2 border-b">
              <button
                onClick={() => setShowTokenModal(true)}
                className="w-full px-3 py-2 bg-purple-600 text-white text-xs font-medium rounded hover:bg-purple-700 transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                生成 MCP Token
              </button>
            </div>

            {/* Type filter */}
            <div className="px-3 py-2 border-b flex gap-1">
              {(['all', 'admin', 'function', 'action'] as const).map(type => (
                <button
                  key={type}
                  onClick={() => setToolType(type)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    toolType === type
                      ? 'bg-blue-100 text-blue-700 font-medium'
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {type === 'all' ? `全部 (${toolCounts.all})` :
                   type === 'admin' ? `Admin (${toolCounts.admin})` :
                   type === 'function' ? `函数 (${toolCounts.function})` :
                   `操作 (${toolCounts.action})`}
                </button>
              ))}
            </div>

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
              {filteredTools.length} / {typeFilteredTools.length} 工具 · 角色: {role}
            </div>
          </div>

          {/* Tool detail + call */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {selectedTool ? (
              <>
                <div className="px-6 py-4 border-b bg-white">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      selectedTool.name.startsWith('ontology_') ? 'bg-purple-100 text-purple-700' :
                      selectedTool.name.startsWith('function:') ? 'bg-green-100 text-green-700' :
                      'bg-orange-100 text-orange-700'
                    }`}>
                      {selectedTool.name.startsWith('ontology_') ? 'Admin' :
                       selectedTool.name.startsWith('function:') ? 'Function' : 'Action'}
                    </span>
                    <h2 className="text-sm font-semibold text-gray-800">{selectedTool.name}</h2>
                  </div>
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
      ) : (
        /* Token 管理面板 */
        <div className="flex-1 flex overflow-hidden">
          <div className="w-96 border-r bg-white flex flex-col flex-shrink-0">
            <div className="px-3 py-2 border-b">
              <button
                onClick={() => setShowTokenModal(true)}
                className="w-full px-3 py-2 bg-purple-600 text-white text-xs font-medium rounded hover:bg-purple-700 transition-colors"
              >
                + 新建 Token
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loadingTokens ? (
                <div className="p-4 text-center text-gray-400 text-sm">加载中...</div>
              ) : tokens.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">暂无 Token</div>
              ) : (
                tokens.map(t => (
                  <div
                    key={t.token}
                    className={`px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${
                      selectedTokenDetail?.token === t.token ? 'bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => handleViewToken(t.token)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-medium text-gray-700 truncate flex-1">
                        {t.description || t.token.slice(0, 24) + '...'}
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); handleDeleteToken(t.token) }}
                        className="text-red-400 hover:text-red-600 text-xs ml-2"
                      >
                        删除
                      </button>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {t.workspace} · {t.role} · {t.toolCount || '默认'} 工具
                    </div>
                    <div className="text-xs text-gray-300 mt-0.5">
                      创建于 {new Date(t.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Token 详情 */}
          <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
            {selectedTokenDetail ? (
              <div className="p-6 space-y-4 overflow-y-auto">
                <div className="bg-white rounded-lg p-4 shadow-sm">
                  <h3 className="text-sm font-semibold text-gray-800 mb-3">Token 信息</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Workspace:</span>
                      <span className="font-medium">{selectedTokenDetail.workspace}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Role:</span>
                      <span className="font-medium">{selectedTokenDetail.role}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">工具数量:</span>
                      <span className="font-medium">{selectedTokenDetail.toolCount || '使用角色默认'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">创建时间:</span>
                      <span className="font-medium">{new Date(selectedTokenDetail.created_at).toLocaleString()}</span>
                    </div>
                    {selectedTokenDetail.expires_at && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">过期时间:</span>
                        <span className="font-medium">{new Date(selectedTokenDetail.expires_at).toLocaleString()}</span>
                      </div>
                    )}
                    {selectedTokenDetail.last_used_at && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">最后使用:</span>
                        <span className="font-medium">{new Date(selectedTokenDetail.last_used_at).toLocaleString()}</span>
                      </div>
                    )}
                    {selectedTokenDetail.base_url && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">服务地址:</span>
                        <span className="font-medium text-blue-600">{selectedTokenDetail.base_url}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-800">Token</h3>
                    <button
                      onClick={() => handleCopyToken(selectedTokenDetail.token)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      {copied ? '已复制!' : '复制'}
                    </button>
                  </div>
                  <div className="bg-gray-900 text-green-400 text-xs font-mono p-3 rounded break-all">
                    {selectedTokenDetail.token}
                  </div>
                </div>

                {selectedTokenDetail.configJson && (
                  <div className="bg-white rounded-lg p-4 shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-gray-800">MCP 配置</h3>
                      <button
                        onClick={() => handleCopyConfig(selectedTokenDetail.configJson!)}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        {copied ? '已复制!' : '一键复制'}
                      </button>
                    </div>
                    <pre className="bg-gray-900 text-gray-300 text-xs font-mono p-3 rounded overflow-x-auto">
                      {selectedTokenDetail.configJson}
                    </pre>
                  </div>
                )}

                {selectedTokenDetail.tools && selectedTokenDetail.tools.length > 0 && (
                  <div className="bg-white rounded-lg p-4 shadow-sm">
                    <h3 className="text-sm font-semibold text-gray-800 mb-2">自定义工具权限</h3>
                    <div className="flex flex-wrap gap-1">
                      {selectedTokenDetail.tools.map(t => (
                        <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                选择左侧的 Token 查看详情
              </div>
            )}
          </div>
        </div>
      )}

      {/* MCP Token 生成模态框 */}
      {showTokenModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-[600px] max-h-[85vh] overflow-hidden flex flex-col">
            <div className="px-4 py-3 border-b flex items-center justify-between flex-shrink-0">
              <h3 className="text-sm font-semibold text-gray-800">生成 MCP Token</h3>
              <button
                onClick={() => { setShowTokenModal(false); setGeneratedToken(null); setSelectedTools([]); setUseCustomTools(false); }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="p-4 space-y-4 overflow-y-auto flex-1">
              {!generatedToken ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-medium text-gray-600 block mb-1">工作空间</label>
                      <select
                        value={tokenWorkspace}
                        onChange={e => setTokenWorkspace(e.target.value)}
                        className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                      >
                        {workspaces.map(ws => (
                          <option key={ws} value={ws}>{ws}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600 block mb-1">角色</label>
                      <select
                        value={tokenRole}
                        onChange={e => setTokenRole(e.target.value)}
                        className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                      >
                        <option value="admin">admin（全部工具）</option>
                        <option value="operator">operator（业务工具）</option>
                        <option value="viewer">viewer（只读工具）</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">描述（可选）</label>
                    <input
                      type="text"
                      value={tokenDesc}
                      onChange={e => setTokenDesc(e.target.value)}
                      placeholder="例如：Claude Desktop 专用"
                      className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">有效期（天，可选）</label>
                    <input
                      type="number"
                      value={tokenExpiry}
                      onChange={e => setTokenExpiry(e.target.value ? parseInt(e.target.value) : '')}
                      placeholder="留空表示永不过期"
                      className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">
                      服务地址（可选）
                      <span className="text-gray-400 font-normal ml-1">用于域名部署</span>
                    </label>
                    <input
                      type="text"
                      value={tokenBaseUrl}
                      onChange={e => setTokenBaseUrl(e.target.value)}
                      placeholder="例如：https://onto.example.com"
                      className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      留空则自动检测当前访问地址
                    </p>
                  </div>

                  {/* 自定义工具权限 */}
                  <div>
                    <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-2">
                      <input
                        type="checkbox"
                        checked={useCustomTools}
                        onChange={e => setUseCustomTools(e.target.checked)}
                        className="rounded"
                      />
                      自定义工具权限（千人千面）
                    </label>
                    
                    {useCustomTools && (
                      <div className="border rounded-lg p-3 max-h-48 overflow-y-auto bg-gray-50">
                        <div className="text-xs text-gray-500 mb-2">
                          已选择 {selectedTools.length} 个工具
                        </div>
                        <div className="space-y-1">
                          {tools.map(t => (
                            <label key={t.name} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-gray-100 p-1 rounded">
                              <input
                                type="checkbox"
                                checked={selectedTools.includes(t.name)}
                                onChange={() => toggleToolSelection(t.name)}
                                className="rounded"
                              />
                              <span className={`px-1 py-0.5 rounded text-xs ${
                                t.name.startsWith('ontology_') ? 'bg-purple-100 text-purple-700' :
                                t.name.startsWith('function:') ? 'bg-green-100 text-green-700' :
                                'bg-orange-100 text-orange-700'
                              }`}>
                                {t.name.startsWith('ontology_') ? 'A' :
                                 t.name.startsWith('function:') ? 'F' : 'Act'}
                              </span>
                              <span className="flex-1 truncate">{t.name}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={handleGenerateToken}
                    disabled={generating}
                    className="w-full px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded hover:bg-purple-700 disabled:opacity-50 transition-colors"
                  >
                    {generating ? '生成中...' : '生成 Token'}
                  </button>
                </>
              ) : (
                <>
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                    <svg className="w-8 h-8 text-green-500 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="text-sm font-medium text-green-800">Token 生成成功！</div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Workspace:</span>
                      <span className="text-xs font-medium text-gray-700">{generatedToken.workspace}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Role:</span>
                      <span className="text-xs font-medium text-gray-700">{generatedToken.role}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">可用工具:</span>
                      <span className="text-xs font-medium text-gray-700">{generatedToken.toolCount} 个</span>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-gray-600">Token</label>
                      <button
                        onClick={() => handleCopyToken(generatedToken.token)}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        {copied ? '已复制!' : '复制'}
                      </button>
                    </div>
                    <div className="bg-gray-900 text-green-400 text-xs font-mono p-3 rounded break-all">
                      {generatedToken.token}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-gray-600">MCP 配置</label>
                      <button
                        onClick={() => handleCopyConfig(generatedToken.configJson!)}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        {copied ? '已复制!' : '一键复制'}
                      </button>
                    </div>
                    <pre className="bg-gray-900 text-gray-300 text-xs font-mono p-3 rounded overflow-x-auto max-h-40">
                      {generatedToken.configJson}
                    </pre>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => { setGeneratedToken(null); setSelectedTools([]); setUseCustomTools(false); }}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded hover:bg-gray-50 transition-colors"
                    >
                      再生成一个
                    </button>
                    <button
                      onClick={() => { setShowTokenModal(false); setGeneratedToken(null); setSelectedTools([]); setUseCustomTools(false); }}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
                    >
                      完成
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
