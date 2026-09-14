import React from 'react'

export type ViewType = 'graph' | 'schema' | 'instances' | 'tools'

interface Props {
  activeView: ViewType
  onViewChange: (view: ViewType) => void
  collapsed: boolean
  onToggleCollapse: () => void
}

const items: { id: ViewType; label: string; icon: React.ReactNode }[] = [
  {
    id: 'graph',
    label: '本体图谱',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
  },
  {
    id: 'schema',
    label: '本体结构',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    ),
  },
  {
    id: 'instances',
    label: '实例浏览',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    id: 'tools',
    label: '工具管理',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
]

export function Sidebar({ activeView, onViewChange, collapsed, onToggleCollapse }: Props) {
  return (
    <div className={`flex flex-col bg-white border-r border-gray-200 transition-all duration-200 ${collapsed ? 'w-12' : 'w-44'}`}>
      {/* Logo */}
      <div className={`flex items-center border-b border-gray-200 ${collapsed ? 'justify-center h-12' : 'px-4 h-12'}`}>
        {!collapsed && <span className="text-sm font-bold text-gray-800">Ontology Hub</span>}
        {collapsed && <span className="text-sm font-bold text-gray-800">OH</span>}
      </div>

      {/* Nav */}
      <div className="flex-1 py-2 space-y-0.5">
        {items.map(item => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`flex items-center gap-3 w-full text-left transition-colors ${
              collapsed ? 'justify-center h-10' : 'px-4 h-10'
            } ${
              activeView === item.id
                ? 'bg-blue-50 text-blue-600 font-medium'
                : 'hover:bg-gray-100 text-gray-600 hover:text-gray-800'
            }`}
            title={item.label}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && <span className="text-sm">{item.label}</span>}
          </button>
        ))}
      </div>

      {/* Collapse toggle */}
      <div className="border-t border-gray-200 p-1">
        <button
          onClick={onToggleCollapse}
          className="flex items-center justify-center w-full h-8 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          title={collapsed ? '展开菜单' : '收起菜单'}
        >
          <svg className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </div>
  )
}
