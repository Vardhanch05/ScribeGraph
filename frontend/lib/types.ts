export type ChunkType = "prose" | "table" | "equation" | "figure_caption"

export interface SourcePaper {
  id: string
  arxiv_id?: string | null
  title: string
  authors: string[]
  source_url?: string | null
  ingested_at: string
  raw_markdown_path: string
  page_count: number
}

export interface PaperChunk {
  id: string
  paper_id: string
  chunk_type: ChunkType
  content: string
  page_number: number
  section_title?: string | null
  order_index: number
  embedding_id?: string | null
}

export interface TableUnit {
  id: string
  paper_id: string
  chunk_id: string
  caption?: string | null
  headers: string[]
  rows: string[][]
  page_number: number
}

export interface EquationUnit {
  id: string
  paper_id: string
  chunk_id: string
  latex: string
  surrounding_context: string
  equation_label?: string | null
  page_number: number
}

export interface CitedSummary {
  id: string
  paper_id: string
  summary: string
  key_claims: string[]
  supporting_chunk_ids: string[]
  generated_at: string
  model_used: string
}

export interface AgentTraceStep {
  step_index: number
  node_name: string
  input_summary: string
  output_summary: string
  tool_calls: Array<Record<string, unknown>>
  timestamp: string
}

export interface QueryResponse {
  answer: string
  citations: string[]
  trace: AgentTraceStep[]
  self_correction_applied: boolean
  confidence_note?: string | null
}

export interface QueryRequest {
  query: string
  paper_ids?: string[]
}

export interface IngestResponse {
  paper_id: string
  status: string
  warnings: string[]
}

export interface PaperDetailResponse {
  paper: SourcePaper
  summary?: CitedSummary | null
}

export interface ChatMessage {
  id: string
  sender: "user" | "assistant"
  content: string
  timestamp: Date
  trace?: AgentTraceStep[]
  selfCorrectionApplied?: boolean
  citations?: string[]
  paperIds?: string[]
  isStreaming?: boolean
}
