"use client"

import React from "react"
import { X, Cpu, CheckCircle2, AlertTriangle, ArrowRight, Layers } from "lucide-react"
import { Button } from "@/components/ui/button"
import { AgentTraceStep } from "@/lib/types"

interface AgentTraceDrawerProps {
  isOpen: boolean
  onClose: () => void
  traceSteps: AgentTraceStep[]
  selfCorrectionApplied?: boolean
}

export function AgentTraceDrawer({
  isOpen,
  onClose,
  traceSteps,
  selfCorrectionApplied,
}: AgentTraceDrawerProps) {
  if (!isOpen) return null

  const getNodeColor = (nodeName: string) => {
    switch (nodeName.toLowerCase()) {
      case "planner":
        return "border-blue-500/50 bg-blue-500/10 text-blue-400"
      case "retriever":
        return "border-purple-500/50 bg-purple-500/10 text-purple-400"
      case "synthesizer":
        return "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
      case "verifier":
        return "border-amber-500/50 bg-amber-500/10 text-amber-400"
      default:
        return "border-border/50 bg-secondary/30 text-foreground"
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-background/95 backdrop-blur-2xl border-l border-border/50 shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="p-4 border-b border-border/40 flex items-center justify-between bg-black/40">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center">
            <Cpu className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground tracking-tight">
              LangGraph Agent Trace
            </h2>
            <p className="text-xs text-muted-foreground">Self-correcting execution log</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={onClose}>
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Self-Correction Warning Badge */}
      {selfCorrectionApplied && (
        <div className="mx-4 mt-4 p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="text-xs font-semibold text-amber-300">Self-Correction Loop Triggered</p>
            <p className="text-[11px] text-amber-200/80 leading-snug">
              The Verifier node detected a context mismatch and re-routed the Retriever to correct the draft answer before final output.
            </p>
          </div>
        </div>
      )}

      {/* Steps List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {traceSteps.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-12">
            <Layers className="w-10 h-10 mb-2 opacity-30 text-primary" />
            <p className="text-sm font-medium">No trace available</p>
            <p className="text-xs max-w-xs mt-1 opacity-70">
              Submit a query to observe Planner, Retriever, Synthesizer, and Verifier execution steps live.
            </p>
          </div>
        ) : (
          traceSteps.map((step, idx) => (
            <div key={idx} className="relative pl-6 border-l border-border/40 space-y-2">
              {/* Step indicator dot */}
              <div className="absolute -left-[9px] top-1 w-4 h-4 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              </div>

              {/* Node Badge */}
              <div className="flex items-center justify-between">
                <span className={`px-2.5 py-0.5 rounded-md border text-xs font-semibold uppercase tracking-wider ${getNodeColor(step.node_name)}`}>
                  Step {step.step_index + 1}: {step.node_name}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  {new Date(step.timestamp).toLocaleTimeString()}
                </span>
              </div>

              {/* Step Input/Output Box */}
              <div className="card-3d bg-secondary/30 rounded-xl p-3 border border-border/30 text-xs space-y-2">
                {step.input_summary && (
                  <div>
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-0.5">
                      Input Context
                    </span>
                    <p className="text-foreground/90 leading-relaxed bg-black/30 p-2 rounded-lg font-mono text-[11px]">
                      {step.input_summary}
                    </p>
                  </div>
                )}

                {step.output_summary && (
                  <div>
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-0.5">
                      Output Result
                    </span>
                    <p className="text-foreground/90 leading-relaxed bg-black/30 p-2 rounded-lg font-mono text-[11px]">
                      {step.output_summary}
                    </p>
                  </div>
                )}

                {step.tool_calls && step.tool_calls.length > 0 && (
                  <div>
                    <span className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider block mb-1">
                      Tool Invocations ({step.tool_calls.length})
                    </span>
                    <div className="space-y-1">
                      {step.tool_calls.map((tc, tcIdx) => (
                        <div key={tcIdx} className="bg-purple-950/30 border border-purple-500/20 p-2 rounded text-[11px] font-mono text-purple-200">
                          {JSON.stringify(tc, null, 2)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border/40 bg-black/40 flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Execution Verified</span>
        </div>
        <span>Total Steps: {traceSteps.length}</span>
      </div>
    </div>
  )
}
