import {
  SourcePaper,
  PaperDetailResponse,
  IngestResponse,
  QueryResponse,
  AgentTraceStep,
} from "./types"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function fetchPapers(): Promise<SourcePaper[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/papers`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    })
    if (!res.ok) throw new Error(`HTTP error ${res.status}`)
    return await res.json()
  } catch (error) {
    console.warn("Backend unavailable, using fallback/empty papers:", error)
    return []
  }
}

export async function fetchPaperDetail(paperId: string): Promise<PaperDetailResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/papers/${paperId}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    })
    if (!res.ok) return null
    return await res.json()
  } catch (error) {
    console.error(`Failed to fetch paper ${paperId}:`, error)
    return null
  }
}

export async function ingestPaper(arxivId?: string, file?: File): Promise<IngestResponse> {
  const formData = new FormData()
  if (arxivId) formData.append("arxiv_id", arxivId)
  if (file) formData.append("file", file)

  const res = await fetch(`${API_BASE_URL}/ingest`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData?.error?.message || errorData?.detail || `Ingestion failed (${res.status})`)
  }

  return await res.json()
}

export async function queryAgent(query: string, paperIds: string[] = []): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, paper_ids: paperIds }),
  })

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData?.error?.message || errorData?.detail || `Agent query failed (${res.status})`)
  }

  return await res.json()
}

export function streamQueryAgent(
  query: string,
  paperIds: string[],
  onTraceStep: (step: AgentTraceStep) => void,
  onFinalResponse: (resp: QueryResponse) => void,
  onError: (err: string) => void
): () => void {
  const controller = new AbortController()

  fetch(`${API_BASE_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, paper_ids: paperIds }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const errorText = await res.text()
        onError(`Server error (${res.status}): ${errorText}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        onError("Response body reader unavailable")
        return
      }

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split("\n\n")
        buffer = events.pop() || ""

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue
          const lines = eventBlock.split("\n")
          let eventType = ""
          let dataStr = ""

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.replace("event: ", "").trim()
            } else if (line.startsWith("data: ")) {
              dataStr = line.replace("data: ", "").trim()
            }
          }

          if (eventType === "trace_step" && dataStr) {
            try {
              const step: AgentTraceStep = JSON.parse(dataStr)
              onTraceStep(step)
            } catch (e) {
              console.error("Failed to parse trace_step:", e)
            }
          } else if (eventType === "final_response" && dataStr) {
            try {
              const resp: QueryResponse = JSON.parse(dataStr)
              onFinalResponse(resp)
            } catch (e) {
              console.error("Failed to parse final_response:", e)
            }
          } else if (eventType === "error" && dataStr) {
            try {
              const errObj = JSON.parse(dataStr)
              onError(errObj.error || "Unknown stream error")
            } catch {
              onError(dataStr)
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "Network error")
      }
    })

  return () => controller.abort()
}

export async function runEvaluation(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE_URL}/eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
  if (!res.ok) {
    throw new Error(`Evaluation failed with status ${res.status}`)
  }
  return await res.json()
}
