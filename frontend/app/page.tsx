"use client"

import React, { useState, useEffect } from "react"
import { Sidebar } from "@/components/sidebar"
import { ChatArea } from "@/components/chat-area"
import { PaperExplorer } from "@/components/paper-explorer"
import { EvalDashboard } from "@/components/eval-dashboard"
import { AgentTraceDrawer } from "@/components/agent-trace-drawer"
import { IngestModal } from "@/components/ingest-modal"
import { fetchPapers } from "@/lib/api"
import { SourcePaper, AgentTraceStep } from "@/lib/types"

export default function Home() {
  const [activeTab, setActiveTab] = useState<"chat" | "explorer" | "eval">("chat")
  const [papers, setPapers] = useState<SourcePaper[]>([])
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([])
  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(320)
  
  // Agent Trace Drawer State
  const [isTraceDrawerOpen, setIsTraceDrawerOpen] = useState(false)
  const [traceDrawerSteps, setTraceDrawerSteps] = useState<AgentTraceStep[]>([])
  const [traceSelfCorrection, setTraceSelfCorrection] = useState(false)

  const refreshPapers = async () => {
    const data = await fetchPapers()
    setPapers(data)
  }

  useEffect(() => {
    refreshPapers()
  }, [])

  const handleTogglePaperSelection = (paperId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((id) => id !== paperId) : [...prev, paperId]
    )
  }

  const handleOpenTraceDrawer = (steps: AgentTraceStep[], selfCorrection?: boolean) => {
    setTraceDrawerSteps(steps)
    setTraceSelfCorrection(!!selfCorrection)
    setIsTraceDrawerOpen(true)
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Left Resizable & Extendable Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenIngestModal={() => setIsIngestModalOpen(true)}
        papers={papers}
        selectedPaperIds={selectedPaperIds}
        onTogglePaperSelection={handleTogglePaperSelection}
        sidebarWidth={sidebarWidth}
        onWidthChange={setSidebarWidth}
      />

      {/* Main Workspace View */}
      {activeTab === "chat" && (
        <ChatArea
          onOpenIngestModal={() => setIsIngestModalOpen(true)}
          onOpenTraceDrawer={handleOpenTraceDrawer}
          papers={papers}
          selectedPaperIds={selectedPaperIds}
        />
      )}

      {activeTab === "explorer" && (
        <PaperExplorer
          onSelectPaperForChat={(paperId) => {
            setSelectedPaperIds([paperId])
            setActiveTab("chat")
          }}
        />
      )}

      {activeTab === "eval" && <EvalDashboard />}

      {/* Slide-over Agent Trace Drawer */}
      <AgentTraceDrawer
        isOpen={isTraceDrawerOpen}
        onClose={() => setIsTraceDrawerOpen(false)}
        traceSteps={traceDrawerSteps}
        selfCorrectionApplied={traceSelfCorrection}
      />

      {/* Ingest arXiv/PDF Modal */}
      <IngestModal
        isOpen={isIngestModalOpen}
        onClose={() => setIsIngestModalOpen(false)}
        onIngestSuccess={() => {
          refreshPapers()
        }}
      />
    </div>
  )
}
