"use client"

import React, { useState } from "react"
import { X, Upload, FileText, CheckCircle2, AlertCircle, Loader2, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ingestPaper } from "@/lib/api"
import { IngestResponse } from "@/lib/types"

interface IngestModalProps {
  isOpen: boolean
  onClose: () => void
  onIngestSuccess: () => void
}

export function IngestModal({ isOpen, onClose, onIngestSuccess }: IngestModalProps) {
  const [activeTab, setActiveTab] = useState<"arxiv" | "pdf">("arxiv")
  const [arxivId, setArxivId] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleIngest = async () => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      if (activeTab === "arxiv") {
        if (!arxivId.trim()) {
          setError("Please enter a valid arXiv ID (e.g. 1706.03762)")
          setLoading(false)
          return
        }
        const resp = await ingestPaper(arxivId.trim(), undefined)
        setResult(resp)
        onIngestSuccess()
      } else {
        if (!selectedFile) {
          setError("Please select a PDF file to upload")
          setLoading(false)
          return
        }
        const resp = await ingestPaper(undefined, selectedFile)
        setResult(resp)
        onIngestSuccess()
      }
    } catch (err: any) {
      setError(err.message || "Ingestion failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-background/95 border border-border/50 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="p-5 border-b border-border/40 flex items-center justify-between bg-black/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/20 border border-primary/40 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground tracking-tight">
                Ingest Research Paper
              </h2>
              <p className="text-xs text-muted-foreground">
                Structure-preserving ingestion into ChromaDB & SQLite
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-border/40 bg-secondary/20 p-1 m-4 rounded-xl">
          <button
            className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "arxiv"
                ? "bg-primary text-primary-foreground shadow"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => {
              setActiveTab("arxiv")
              setError(null)
              setResult(null)
            }}
          >
            arXiv Paper ID
          </button>
          <button
            className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "pdf"
                ? "bg-primary text-primary-foreground shadow"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => {
              setActiveTab("pdf")
              setError(null)
              setResult(null)
            }}
          >
            Upload PDF Document
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {activeTab === "arxiv" ? (
            <div className="space-y-3">
              <label className="text-xs font-medium text-muted-foreground block">
                arXiv Paper Identifier
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g. 1706.03762 or 2307.09288"
                  value={arxivId}
                  onChange={(e) => setArxivId(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/50 rounded-xl px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors font-mono"
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                ScribeGraph fetches the paper, parses formulas via LlamaParse, extracts Prose/Tables/Equations, and creates multi-collection ChromaDB embeddings.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <label className="text-xs font-medium text-muted-foreground block">
                Local PDF File
              </label>
              <div
                className="border-2 border-dashed border-border/60 hover:border-primary/60 rounded-xl p-6 text-center cursor-pointer transition-colors bg-secondary/20 hover:bg-secondary/40 flex flex-col items-center justify-center space-y-2"
                onClick={() => document.getElementById("pdf-file-input")?.click()}
              >
                <Upload className="w-8 h-8 text-primary/70 mb-1" />
                {selectedFile ? (
                  <div className="flex items-center gap-2 text-sm text-foreground font-medium">
                    <FileText className="w-4 h-4 text-primary" />
                    <span>{selectedFile.name}</span>
                    <span className="text-xs text-muted-foreground">
                      ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                    </span>
                  </div>
                ) : (
                  <>
                    <p className="text-xs font-medium text-foreground">Click to select or drag a PDF file</p>
                    <p className="text-[11px] text-muted-foreground">Supports academic papers up to 50MB</p>
                  </>
                )}
                <input
                  id="pdf-file-input"
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setSelectedFile(e.target.files[0])
                    }
                  }}
                />
              </div>
            </div>
          )}

          {/* Feedback messages */}
          {error && (
            <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex flex-col space-y-1">
              <div className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Paper Ingested Successfully!</span>
              </div>
              <p className="text-[11px] text-emerald-200/80 font-mono">
                Paper UUID: {result.paper_id}
              </p>
              {result.warnings && result.warnings.length > 0 && (
                <div className="mt-1 pt-1 border-t border-emerald-500/20 text-[10px] text-amber-300">
                  Warnings: {result.warnings.join(", ")}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-border/40 bg-black/40 flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={loading} className="text-xs">
            Cancel
          </Button>
          <Button
            onClick={handleIngest}
            disabled={loading}
            className="btn-3d btn-glow gap-2 bg-gradient-to-br from-primary via-gray-900 to-black hover:from-gray-900 hover:to-black text-white text-xs px-5 shadow-lg"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Processing Ingestion...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Start Ingestion</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
