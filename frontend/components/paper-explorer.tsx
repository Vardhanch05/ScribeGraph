"use client"

import React, { useState, useEffect } from "react"
import { SourcePaper, PaperDetailResponse } from "@/lib/types"
import { fetchPapers, fetchPaperDetail } from "@/lib/api"
import { BookOpen, FileText, CheckCircle2, ListFilter, Search, Hash, Loader2, Award, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"

interface PaperExplorerProps {
  onSelectPaperForChat?: (paperId: string) => void
}

export function PaperExplorer({ onSelectPaperForChat }: PaperExplorerProps) {
  const [papers, setPapers] = useState<SourcePaper[]>([])
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PaperDetailResponse | null>(null)
  const [loadingPapers, setLoadingPapers] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  useEffect(() => {
    async function load() {
      setLoadingPapers(true)
      const data = await fetchPapers()
      setPapers(data)
      if (data.length > 0) {
        setSelectedPaperId(data[0].id)
      }
      setLoadingPapers(false)
    }
    load()
  }, [])

  useEffect(() => {
    if (!selectedPaperId) return
    async function loadDetail() {
      setLoadingDetail(true)
      const res = await fetchPaperDetail(selectedPaperId!)
      setDetail(res)
      setLoadingDetail(false)
    }
    loadDetail()
  }, [selectedPaperId])

  const filteredPapers = papers.filter(
    (p) =>
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.arxiv_id && p.arxiv_id.includes(searchQuery)) ||
      p.authors.some((a) => a.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-background">
      {/* Sidebar: Ingested Papers List */}
      <div className="w-80 border-r border-border/40 flex flex-col bg-sidebar/50">
        <div className="p-4 border-b border-border/40 space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            <h2 className="text-sm font-semibold text-foreground tracking-tight">Paper Explorer</h2>
            <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-mono border border-primary/30">
              {papers.length}
            </span>
          </div>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search title, arXiv ID, author..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-secondary/40 border border-border/40 rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingPapers ? (
            <div className="p-6 text-center text-muted-foreground flex flex-col items-center">
              <Loader2 className="w-6 h-6 animate-spin text-primary mb-2" />
              <p className="text-xs">Loading ingested papers...</p>
            </div>
          ) : filteredPapers.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground text-xs">No papers found</div>
          ) : (
            filteredPapers.map((paper) => {
              const isSelected = paper.id === selectedPaperId
              return (
                <button
                  key={paper.id}
                  onClick={() => setSelectedPaperId(paper.id)}
                  className={`w-full text-left p-3 rounded-xl transition-all border ${
                    isSelected
                      ? "bg-primary/10 border-primary/40 text-foreground shadow"
                      : "bg-transparent border-transparent hover:bg-secondary/30 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <p className="text-xs font-semibold line-clamp-2 leading-snug">{paper.title}</p>
                  <div className="flex items-center justify-between mt-2 text-[10px] opacity-80">
                    <span className="font-mono">{paper.arxiv_id ? `arXiv:${paper.arxiv_id}` : "PDF Ingest"}</span>
                    <span>{paper.page_count} pages</span>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Main Detail Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {!selectedPaperId ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
            <FileText className="w-12 h-12 opacity-30 text-primary mb-3" />
            <p className="text-sm font-medium">Select a paper to explore details</p>
          </div>
        ) : loadingDetail ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
            <p className="text-xs">Loading paper structure & claims...</p>
          </div>
        ) : !detail ? (
          <div className="p-6 text-center text-muted-foreground text-xs">Failed to load paper details</div>
        ) : (
          <>
            {/* Header / Meta Card */}
            <div className="card-3d bg-gradient-to-br from-secondary/60 via-secondary/40 to-secondary/30 rounded-2xl p-6 border border-border/50 shadow-xl space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-full bg-primary/20 text-primary text-xs font-mono border border-primary/30">
                      {detail.paper.arxiv_id ? `arXiv:${detail.paper.arxiv_id}` : "Custom Upload"}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">
                      Ingested: {new Date(detail.paper.ingested_at).toLocaleDateString()}
                    </span>
                  </div>
                  <h1 className="text-2xl font-bold text-foreground tracking-tight leading-snug">
                    {detail.paper.title}
                  </h1>
                  <p className="text-xs text-muted-foreground">
                    Authors: {detail.paper.authors.join(", ") || "Unknown"}
                  </p>
                </div>

                {onSelectPaperForChat && (
                  <Button
                    onClick={() => onSelectPaperForChat(detail.paper.id)}
                    className="btn-3d btn-glow gap-2 bg-gradient-to-br from-primary via-gray-900 to-black text-white text-xs px-4 py-2"
                  >
                    <span>Query in Chat</span>
                  </Button>
                )}
              </div>

              <div className="flex items-center gap-6 pt-3 border-t border-border/30 text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <Hash className="w-4 h-4 text-primary" />
                  <span>UUID: <span className="font-mono text-foreground/80">{detail.paper.id}</span></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-purple-400" />
                  <span>{detail.paper.page_count} Pages</span>
                </div>
                {detail.paper.arxiv_id && (
                  <a
                    href={`https://arxiv.org/abs/${detail.paper.arxiv_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-primary hover:underline ml-auto"
                  >
                    <span>View on arXiv</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>

            {/* Cited Summary & Key Scientific Claims */}
            {detail.summary && (
              <div className="space-y-6">
                {/* Summary Section */}
                <div className="card-3d bg-secondary/30 rounded-2xl p-6 border border-border/40 space-y-3">
                  <div className="flex items-center gap-2">
                    <Award className="w-5 h-5 text-amber-400" />
                    <h3 className="text-base font-semibold text-foreground">LLM Generated Cited Summary</h3>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-black/40 text-muted-foreground font-mono border border-border/30 ml-auto">
                      Model: {detail.summary.model_used}
                    </span>
                  </div>
                  <p className="text-sm text-foreground/90 leading-relaxed font-normal bg-black/20 p-4 rounded-xl border border-border/30">
                    {detail.summary.summary}
                  </p>
                </div>

                {/* Key Claims Section */}
                {detail.summary.key_claims && detail.summary.key_claims.length > 0 && (
                  <div className="card-3d bg-secondary/30 rounded-2xl p-6 border border-border/40 space-y-4">
                    <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      Key Scientific Claims ({detail.summary.key_claims.length})
                    </h3>
                    <div className="grid gap-3">
                      {detail.summary.key_claims.map((claim, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-xl bg-black/30 border border-border/30 flex items-start gap-3 text-xs text-foreground/90 leading-relaxed"
                        >
                          <span className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold flex items-center justify-center shrink-0 text-[10px] border border-emerald-500/30">
                            {idx + 1}
                          </span>
                          <p>{claim}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
