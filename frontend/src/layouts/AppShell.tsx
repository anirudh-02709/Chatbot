import React, { useState } from 'react'

interface AppShellProps {
  sidebar: (props: { onCloseMobile: () => void }) => React.ReactNode
  children: (props: { onToggleSidebar: () => void }) => React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({ sidebar, children }) => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)

  const toggleMobileSidebar = () => {
    setIsMobileSidebarOpen((prev) => !prev)
  }

  const closeMobileSidebar = () => {
    setIsMobileSidebarOpen(false)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-0 text-text-primary">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex shrink-0 h-full">
        {sidebar({ onCloseMobile: closeMobileSidebar })}
      </div>

      {/* Mobile Drawer Overlay */}
      {isMobileSidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 transition-opacity"
            onClick={closeMobileSidebar}
            aria-hidden="true"
          />

          {/* Drawer Panel */}
          <div className="relative flex-1 max-w-xs w-full bg-surface-1 shadow-xl z-10">
            {sidebar({ onCloseMobile: closeMobileSidebar })}
          </div>
        </div>
      )}

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {children({ onToggleSidebar: toggleMobileSidebar })}
      </div>
    </div>
  )
}
