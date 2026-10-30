"use client"

import React, { useState } from "react"
import {
  MessageSquare,
  BookOpen,
  BarChart3,
  Plus,
  Cpu,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
  GripVertical,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { SourcePaper } from "@/lib/types"

interface SidebarProps {
  activeTab: "chat" | "explorer" | "eval"
  onTabChange: (tab: "chat" | "explorer" | "eval") => void
  onOpenIngestModal: () => void
  papers: SourcePaper[]
  selectedPaperIds: string[]
  onTogglePaperSelection: (paperId: string) => void
  sidebarWidth: number
  onWidthChange: (width: number) => void
}

export function Sidebar({
  activeTab,
  onTabChange,
  onOpenIngestModal,
  papers,
  selectedPaperIds,
  onTogglePaperSelection,
  sidebarWidth,
  onWidthChange,
}: SidebarProps) {
  const [isResizing, setIsResizing] = useState(false)
  const isCollapsed = sidebarWidth < 140

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    const startX = e.clientX
    const startWidth = sidebarWidth

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX
      const newWidth = Math.min(Math.max(startWidth + deltaX, 64), 550)
      onWidthChange(newWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = "default"
      document.body.style.userSelect = "auto"
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
  }

  const handleToggleCollapse = () => {
    if (isCollapsed) {
      onWidthChange(320)
    } else {
      onWidthChange(64)
    }
  }

  return (
    <aside
      style={{ width: `${sidebarWidth}px` }}
      className={`relative bg-sidebar border-r border-sidebar-border flex flex-col h-full shrink-0 ${
        isResizing ? "transition-none select-none" : "transition-[width] duration-150 ease-out"
      }`}
    >
      {/* Resizable Drag Handle Border */}
      <div
        onMouseDown={handleMouseDown}
        onDoubleClick={handleToggleCollapse}
        title="Click and drag to extend width (Double click to toggle)"
        className="absolute top-0 right-0 bottom-0 w-2.5 -mr-1.25 z-30 cursor-col-resize group flex items-center justify-center hover:bg-primary/40 active:bg-primary transition-colors"
      >
        <div className="w-1 h-6 rounded-full bg-border group-hover:bg-primary transition-colors flex items-center justify-center">
          <GripVertical className="w-2 h-3 text-muted-foreground group-hover:text-primary-foreground opacity-0 group-hover:opacity-100" />
        </div>
      </div>

      {/* Brand Header */}
      <div className="p-3.5 flex items-center justify-between border-b border-sidebar-border shrink-0 overflow-hidden">
        {!isCollapsed ? (
          <>
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary via-purple-600 to-indigo-700 flex items-center justify-center shadow-lg shrink-0">
                <Cpu className="w-4 h-4 text-white" />
              </div>
              <div className="min-w-0">
                <span className="text-sm font-bold text-sidebar-foreground tracking-tight block leading-tight truncate">
                  ScribeGraph
                </span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleToggleCollapse}
              title="Collapse Sidebar"
              className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0"
            >
              <PanelLeftClose className="w-4 h-4" />
            </Button>
          </>
        ) : (
          <div className="w-full flex flex-col items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleToggleCollapse}
              title="Extend Sidebar"
              className="h-8 w-8 text-primary hover:bg-primary/20"
            >
              <PanelLeftOpen className="w-5 h-5" />
            </Button>
          </div>
        )}
      </div>

      {/* Primary Action Button */}
      <div className="p-2 shrink-0">
        {!isCollapsed ? (
          <Button
            onClick={onOpenIngestModal}
            className="btn-3d btn-glow w-full justify-center gap-2 bg-gradient-to-br from-primary via-gray-900 to-black hover:from-gray-900 hover:to-black text-white font-medium text-xs py-2 shadow-xl"
          >
            <Plus className="w-4 h-4" />
            <span>Ingest arXiv / PDF Paper</span>
          </Button>
        ) : (
          <Button
            onClick={onOpenIngestModal}
            size="icon"
            title="Ingest Paper"
            className="btn-3d btn-glow w-full h-9 justify-center bg-gradient-to-br from-primary via-gray-900 to-black text-white shadow-xl"
          >
            <Plus className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Main Navigation Section */}
      <div className="px-2 flex-1 min-h-0 flex flex-col space-y-4 py-2 overflow-hidden">
        <div className="shrink-0">
          {!isCollapsed && (
            <h3 className="px-2 mb-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              Navigation
            </h3>
          )}
          <div className="space-y-1">
            <Button
              variant={activeTab === "chat" ? "secondary" : "ghost"}
              onClick={() => onTabChange("chat")}
              title="Research Chat"
              className={`btn-3d w-full ${
                isCollapsed ? "justify-center px-0 h-9" : "justify-start gap-3 px-2.5 text-xs"
              } font-medium ${
                activeTab === "chat"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground border border-sidebar-border"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              <MessageSquare className="w-4 h-4 text-primary shrink-0" />
              {!isCollapsed && <span className="truncate">Research Chat</span>}
            </Button>

            <Button
              variant={activeTab === "explorer" ? "secondary" : "ghost"}
              onClick={() => onTabChange("explorer")}
              title="Paper Explorer"
              className={`btn-3d w-full ${
                isCollapsed ? "justify-center px-0 h-9" : "justify-start gap-3 px-2.5 text-xs"
              } font-medium ${
                activeTab === "explorer"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground border border-sidebar-border"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              <BookOpen className="w-4 h-4 text-purple-400 shrink-0" />
              {!isCollapsed && <span className="truncate">Paper Explorer</span>}
            </Button>

            <Button
              variant={activeTab === "eval" ? "secondary" : "ghost"}
              onClick={() => onTabChange("eval")}
              title="5-D Eval Dashboard"
              className={`btn-3d w-full ${
                isCollapsed ? "justify-center px-0 h-9" : "justify-start gap-3 px-2.5 text-xs"
              } font-medium ${
                activeTab === "eval"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground border border-sidebar-border"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              <BarChart3 className="w-4 h-4 text-emerald-400 shrink-0" />
              {!isCollapsed && <span className="truncate">5-D Eval Dashboard</span>}
            </Button>
          </div>
        </div>

        {/* Ingested Paper Scope Filter (Fully Expandable) */}
        <div className="flex-1 min-h-0 flex flex-col">
          {!isCollapsed ? (
            <>
              <div className="px-2 mb-2 flex items-center justify-between shrink-0">
                <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider truncate">
                  Ingested Papers ({papers.length})
                </h3>
                <button
                  onClick={() => {
                    // Quick select/clear all
                    if (selectedPaperIds.length === papers.length) {
                      onTogglePaperSelection("CLEAR_ALL")
                    }
                  }}
                  className="text-[10px] text-primary font-mono shrink-0 hover:underline cursor-pointer"
                >
                  {selectedPaperIds.length === 0 ? "All" : `${selectedPaperIds.length} Sel.`}
                </button>
              </div>

              {/* Scrollable list taking ALL remaining vertical height */}
              <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 pr-1">
                {papers.length === 0 ? (
                  <p className="px-2 py-2 text-[11px] text-muted-foreground italic">
                    No papers ingested yet.
                  </p>
                ) : (
                  papers.map((paper) => {
                    const isChecked = selectedPaperIds.includes(paper.id)
                    return (
                      <div
                        key={paper.id}
                        onClick={() => onTogglePaperSelection(paper.id)}
                        className={`p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                          isChecked
                            ? "bg-primary/10 border-primary/40 text-foreground font-medium"
                            : "bg-sidebar-accent/30 border-sidebar-border/50 text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}}
                            className="mt-0.5 rounded border-border text-primary focus:ring-primary h-3.5 w-3.5 shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="truncate text-xs leading-snug">{paper.title}</p>
                            <p className="text-[10px] opacity-70 font-mono mt-0.5">
                              {paper.arxiv_id ? `arxiv:${paper.arxiv_id}` : `ID: ${paper.id.slice(0, 8)}...`}
                            </p>
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-1.5 py-1">
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30"
                title={`${papers.length} Papers Ingested`}
              >
                {papers.length}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* System Status Footer */}
      {!isCollapsed && (
        <div className="p-2.5 shrink-0">
          <div className="card-3d bg-sidebar-accent/60 rounded-xl p-2.5 border border-sidebar-border space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-sidebar-foreground flex items-center gap-1.5 text-[10px]">
                <Sparkles className="w-3 h-3 text-amber-400" />
                Pipeline Status
              </span>
              <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 font-mono text-[9px] border border-emerald-500/30">
                READY
              </span>
            </div>

            <div className="space-y-0.5 text-[10px] text-muted-foreground">
              <div className="flex justify-between">
                <span>Model:</span>
                <span className="font-mono text-foreground/80">Llama-3.3-70B</span>
              </div>
              <div className="flex justify-between">
                <span>Vector DB:</span>
                <span className="font-mono text-foreground/80">ChromaDB</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
