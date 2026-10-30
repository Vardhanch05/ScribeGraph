"use client"

import React, { useState } from "react"
import {
  Upload,
  ArrowUp,
  Paperclip,
  Cpu,
  Sparkles,
  AlertTriangle,
  BookOpen,
  Loader2,
  Layers,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ParticleOrb } from "@/components/particle-orb"
import { FormattedMessage } from "@/components/formatted-message"
import { ChatMessage, AgentTraceStep, SourcePaper } from "@/lib/types"
import { streamQueryAgent, queryAgent } from "@/lib/api"

interface ChatAreaProps {
  onOpenIngestModal: () => void
  onOpenTraceDrawer: (steps: AgentTraceStep[], selfCorrection?: boolean) => void
  papers: SourcePaper[]
  selectedPaperIds: string[]
}

export function ChatArea({
  onOpenIngestModal,
  onOpenTraceDrawer,
  papers,
  selectedPaperIds,
}: ChatAreaProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputQuery, setInputQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [currentTraceSteps, setCurrentTraceSteps] = useState<AgentTraceStep[]>([])

  const quickPrompts = [
    "Explain the self-attention equation and matrix dimensions",
    "Compare FlashAttention SRAM Tiling vs Standard Attention",
    "Extract Adam Optimizer learning rate equations & LaTeX formulas",
  ]

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputQuery
    if (!textToSend.trim() || loading) return

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      content: textToSend,
      timestamp: new Date(),
      paperIds: selectedPaperIds,
    }

    setMessages((prev) => [...prev, userMsg])
    setInputQuery("")
    setLoading(true)
    setCurrentTraceSteps([])

    const assistantMsgId = (Date.now() + 1).toString()

    const placeholderMsg: ChatMessage = {
      id: assistantMsgId,
      sender: "assistant",
      content: "Analyzing research papers via LangGraph agent loop...",
      timestamp: new Date(),
      isStreaming: true,
      trace: [],
    }

    setMessages((prev) => [...prev, placeholderMsg])

    try {
      let accumulatedTrace: AgentTraceStep[] = []

      streamQueryAgent(
        textToSend,
        selectedPaperIds,
        (step) => {
          accumulatedTrace = [...accumulatedTrace, step]
          setCurrentTraceSteps(accumulatedTrace)
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: `Executing ${step.node_name} (Step ${step.step_index + 1})...`,
                    trace: accumulatedTrace,
                  }
                : msg
            )
          )
        },
        (finalResp) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: finalResp.answer,
                    citations: finalResp.citations,
                    trace: finalResp.trace || accumulatedTrace,
                    selfCorrectionApplied: finalResp.self_correction_applied,
                    isStreaming: false,
                  }
                : msg
            )
          )
          setLoading(false)
        },
        async (errMessage) => {
          console.warn("SSE stream failed, falling back to sync endpoint:", errMessage)
          try {
            const syncResp = await queryAgent(textToSend, selectedPaperIds)
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: syncResp.answer,
                      citations: syncResp.citations,
                      trace: syncResp.trace,
                      selfCorrectionApplied: syncResp.self_correction_applied,
                      isStreaming: false,
                    }
                  : msg
              )
            )
          } catch (syncErr: any) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: `Execution failed: ${syncErr.message || "Unable to reach ScribeGraph API"}`,
                      isStreaming: false,
                    }
                  : msg
              )
            )
          } finally {
            setLoading(false)
          }
        }
      )
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: `Failed to initiate query: ${err.message}`,
                isStreaming: false,
              }
            : msg
        )
      )
      setLoading(false)
    }
  }

  return (
    <main className="flex-1 flex flex-col relative overflow-hidden h-full bg-background min-w-0">
      <div className="absolute inset-0 bg-gradient-to-br from-black via-gray-950 to-black" />

      {/* Animated gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="shader-orb shader-orb-1" />
        <div className="shader-orb shader-orb-2" />
        <div className="shader-orb shader-orb-3" />
      </div>

      {/* Animated grid overlay */}
      <div className="absolute inset-0 opacity-[0.12] grid-background pointer-events-none" />

      {/* Top Header */}
      <header className="relative z-10 flex items-center justify-between px-6 py-2.5 border-b border-border/40 backdrop-blur-md bg-background/30 shrink-0">
        <div className="flex items-center gap-3">
          <div className="btn-3d btn-glow gap-2 bg-gradient-to-br from-secondary/90 to-secondary/70 text-foreground px-3 py-1 rounded-xl border border-border/30 shadow-md text-xs font-semibold flex items-center">
            <Cpu className="w-4 h-4 text-primary" />
            <span>ScribeGraph Agent (Groq Llama-3.3-70B)</span>
          </div>

          <div className="px-3 py-1 rounded-xl bg-primary/10 border border-primary/30 text-primary text-xs font-mono flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            <span>
              {selectedPaperIds.length === 0
                ? `Scope: All Ingested (${papers.length})`
                : `Scope: ${selectedPaperIds.length} Selected Paper(s)`}
            </span>
          </div>
        </div>
      </header>

      {/* Content Area: Chat or Welcome Screen */}
      <div className="relative z-10 flex-1 overflow-y-auto px-6 py-4 flex flex-col justify-between min-h-0">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center my-auto">
            <div className="relative mb-4 scale-90">
              <ParticleOrb />
            </div>

            <h1 className="text-2xl font-bold text-foreground mb-2 text-center tracking-tight">
              Agentic Technical Research Assistant
            </h1>
            <p className="text-xs text-muted-foreground text-center max-w-lg mb-6 leading-relaxed">
              Structure-preserving PDF ingestion with type-aware semantic retrieval across LaTeX equations, tables, and prose narrative.
            </p>

            {/* Quick Action Cards */}
            <div className="flex flex-wrap justify-center gap-2.5 max-w-3xl mb-6">
              {quickPrompts.map((prompt, idx) => (
                <Button
                  key={idx}
                  variant="secondary"
                  onClick={() => handleSend(prompt)}
                  className="btn-3d btn-glow gap-2 bg-secondary/50 text-foreground hover:bg-secondary/80 backdrop-blur-sm text-xs font-medium border border-border/40 py-2 px-3.5 shadow-md text-left"
                >
                  <Sparkles className="w-3.5 h-3.5 text-primary shrink-0" />
                  <span className="truncate max-w-sm">{prompt}</span>
                </Button>
              ))}
            </div>
          </div>
        ) : (
          /* Broad Message Container */
          <div className="space-y-4 max-w-6xl w-full mx-auto pb-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"} space-y-1.5`}
              >
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono px-1">
                  <span>{msg.sender === "user" ? "User Query" : "ScribeGraph Agent"}</span>
                  <span>•</span>
                  <span>{msg.timestamp.toLocaleTimeString()}</span>
                </div>

                <div
                  className={`rounded-2xl p-4 border shadow-xl w-full ${
                    msg.sender === "user"
                      ? "bg-primary/20 border-primary/40 text-foreground max-w-4xl"
                      : "bg-secondary/40 border-border/50 backdrop-blur-xl max-w-full"
                  }`}
                >
                  {msg.sender === "user" ? (
                    <p className="text-xs font-medium leading-relaxed">{msg.content}</p>
                  ) : (
                    <div className="space-y-3">
                      {msg.isStreaming ? (
                        <div className="flex items-center gap-3 text-xs text-primary py-1 font-mono">
                          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                          <span>{msg.content}</span>
                        </div>
                      ) : (
                        <FormattedMessage content={msg.content} />
                      )}

                      {/* Self-Correction Warning Badge */}
                      {msg.selfCorrectionApplied && (
                        <div className="mt-2 p-2 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center gap-2 text-xs text-amber-300">
                          <AlertTriangle className="w-4 h-4 shrink-0" />
                          <span>Verifier Node detected context gap & auto-corrected answer</span>
                        </div>
                      )}

                      {/* Execution Trace Button */}
                      {msg.trace && msg.trace.length > 0 && (
                        <div className="pt-2 border-t border-border/30 flex items-center justify-between text-xs">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onOpenTraceDrawer(msg.trace!, msg.selfCorrectionApplied)}
                            className="btn-3d gap-2 text-primary hover:text-primary-foreground hover:bg-primary/20 text-xs px-2.5 py-1 h-7"
                          >
                            <Layers className="w-3.5 h-3.5" />
                            <span>View Agent Execution Trace ({msg.trace.length} Steps)</span>
                          </Button>

                          {msg.citations && msg.citations.length > 0 && (
                            <span className="text-[10px] text-muted-foreground font-mono">
                              Citations: {msg.citations.length} chunk UUIDs
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Shorter & Broader Input Box */}
        <div className="w-full max-w-6xl mx-auto mt-2 shrink-0">
          <div className="input-3d bg-gradient-to-br from-secondary/70 via-secondary/60 to-secondary/50 backdrop-blur-xl rounded-xl border border-border/50 p-2.5 shadow-2xl space-y-2">
            <textarea
              placeholder="Ask anything about ingested papers, LaTeX formulas, or dataset tables..."
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              className="w-full bg-transparent border-none outline-none resize-none text-foreground placeholder:text-muted-foreground text-xs min-h-[38px] max-h-[120px] font-normal leading-relaxed py-0.5"
            />

            <div className="flex items-center justify-between pt-1.5 border-t border-border/30">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onOpenIngestModal}
                  className="btn-3d gap-1.5 text-muted-foreground hover:text-foreground text-[11px] h-7 px-2.5"
                >
                  <Paperclip className="w-3 h-3" />
                  Attach arXiv / PDF
                </Button>
              </div>

              <Button
                onClick={() => handleSend()}
                disabled={loading || !inputQuery.trim()}
                size="icon"
                className="btn-3d btn-glow h-7 w-7 rounded-lg bg-gradient-to-br from-primary via-gray-900 to-black hover:from-gray-900 hover:to-black text-white shadow-lg shrink-0"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ArrowUp className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
