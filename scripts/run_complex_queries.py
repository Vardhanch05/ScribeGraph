import asyncio
import json
import os
from uuid import uuid4

# Ensure MOCK_LLM is set for deterministic local execution
os.environ["MOCK_LLM"] = "true"

from quantinsight.agent.graph import run_agent
from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.storage.sqlite_store import init_db
from quantinsight.schemas.models import CitedSummary
from unittest.mock import patch, AsyncMock
from datetime import datetime, UTC


async def main():
    init_db()

    # Paper 1 Markdown (PatchTST & Multivariate Time Series)
    markdown_paper_1 = """# Section 1: Introduction to PatchTST
PatchTST introduces channel-independence and time-series patching for multivariate forecasting.
Each univariate series is split into overlapping patches of length $P$ and stride $S$.

---
# Section 2: Mathematical Formulation
The patching transformation maps input $X_i \\in \\mathbb{R}^{L}$ into $N$ patches:
$$
P_i = \\text{Patchify}(X_i, P, S) \\in \\mathbb{R}^{N \\times P}
$$
where $N = \\lfloor \\frac{L - P}{S} \\rfloor + 2$ is the number of patches, $P$ is patch length, and $S$ is stride.
The embedding layer projects each patch to dimension $d_{model}$ using matrix $W_P \\in \\mathbb{R}^{P \\times d_{model}}$:
$$
Z_i = P_i W_P + E_{pos}
$$
where $E_{pos} \\in \\mathbb{R}^{N \\times d_{model}}$ denotes positional encodings.

---
# Section 3: Empirical Benchmark Results
Table 1: Multivariate Forecasting MSE Comparison across Horizons.
| Model | Horizon 96 | Horizon 192 | Horizon 336 | Horizon 720 |
|---|---|---|---|---|
| PatchTST (Ours) | 0.149 | 0.194 | 0.245 | 0.321 |
| DLinear | 0.176 | 0.218 | 0.265 | 0.342 |
| Autoformer | 0.255 | 0.281 | 0.339 | 0.422 |
| Informer | 0.365 | 0.412 | 0.518 | 0.675 |
"""

    # Paper 2 Markdown (Relational Graph Attention & Scaling)
    markdown_paper_2 = """# Section 1: Relational Graph Attention
Multi-Head Relational Attention computes node relation features over arbitrary graph topologies.
Channel dependence can introduce inter-series noise if cross-variable correlations change over time.

---
# Section 2: Attention Relation Equations
The core scaled dot-product relation formula is defined as:
$$
\\text{Attention}(Q, K, V) = \\sigma\\left(\\frac{Q K^T}{\\sqrt{d_k}}\\right) V
$$
where $Q, K, V \\in \\mathbb{R}^{N \\times d_k}$ are query, key, and value projection matrices, and $\\sqrt{d_k}$ is the temperature scaling parameter preventing gradient vanishing in high dimensions.

---
# Section 3: Baseline Comparison Results
Table 2: Classification Accuracy and Error Metrics across Graph Topologies.
| Model Baseline | Accuracy | F1-Score | MAE |
|---|---|---|---|
| Relational Graph Attn | 98.2% | 0.978 | 0.042 |
| GCN Baseline | 89.4% | 0.885 | 0.115 |
| GAT Baseline | 91.1% | 0.902 | 0.098 |
"""

    # Mock parse_pdf and generate_cited_summary for ingestion
    def make_mock_summary(paper_id):
        return CitedSummary(
            id=uuid4(),
            paper_id=paper_id,
            summary="Mock paper summary.",
            key_claims=["Key Claim 1", "Key Claim 2"],
            supporting_chunk_ids=[],
            generated_at=datetime.now(UTC),
            model_used="mock-model",
        )

    with patch("quantinsight.ingestion.pipeline.parse_pdf", new_callable=AsyncMock) as mock_parse:
        with patch("quantinsight.ingestion.pipeline.generate_cited_summary") as mock_summary:
            mock_summary.side_effect = lambda paper_id, chunks, api_key, model: make_mock_summary(paper_id)

            mock_parse.return_value = markdown_paper_1
            paper_id_1, _ = await ingest_paper(
                arxiv_id="2211.14730",
                title="PatchTST: Long-term Forecasting with Patching",
                authors=["Yuqi Nie", "Hashem Namazi"],
                api_key="mock",
                groq_api_key="mock",
            )

            mock_parse.return_value = markdown_paper_2
            paper_id_2, _ = await ingest_paper(
                arxiv_id="2303.09999",
                title="Multi-Head Relational Graph Attention",
                authors=["Alice Smith", "Bob Jones"],
                api_key="mock",
                groq_api_key="mock",
            )

    print(f"Ingested Paper 1 ID: {paper_id_1}")
    print(f"Ingested Paper 2 ID: {paper_id_2}\n")

    complex_queries = [
        (
            "Query 1: Mathematical Formula & Parameter Extraction",
            "Extract and compare the mathematical formulation for time-series patching $P_i = \\text{Patchify}(X_i, P, S)$ versus the scaled dot-product relation formula \\sigma(Q K^T / \\sqrt{d_k}), detailing the parameters and dimension roles.",
            [paper_id_1, paper_id_2],
        ),
        (
            "Query 2: Multi-Paper Tabular Benchmark Comparison",
            "Compare the empirical benchmark metrics across models in Table 1 (MSE across forecasting horizons 96-720) and Table 2 (Accuracy and F1-Score), citing exact table rows.",
            [paper_id_1, paper_id_2],
        ),
        (
            "Query 3: Architectural Strategy & Noise Mitigation",
            "Analyze how channel-independence in multivariate time-series forecasting mitigates inter-series noise compared to relational graph attention mechanisms.",
            [paper_id_1, paper_id_2],
        ),
    ]

    results_output = []

    for title, q, pids in complex_queries:
        print(f"=" * 80)
        print(f"RUNNING: {title}")
        print(f"QUERY: {q}")
        print(f"=" * 80)

        res = await run_agent(query=q, paper_ids=pids)
        res_json = res.model_dump(mode="json")
        results_output.append({
            "title": title,
            "query": q,
            "response": res_json
        })

        print("\n--- OUTPUT QUERY RESPONSE ---")
        print(json.dumps(res_json, indent=2))
        print("\n")

    # Save to JSON file for reference
    os.makedirs("artifacts/complex_query_outputs", exist_ok=True)
    with open("artifacts/complex_query_outputs/results.json", "w") as f:
        json.dump(results_output, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
