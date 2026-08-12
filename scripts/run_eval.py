import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

from quantinsight.agent.graph import run_agent
from quantinsight.storage.sqlite_store import (
    get_chunk_by_id,
    get_table_by_chunk_id,
    get_equation_by_chunk_id,
)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_PATH = os.path.join(WORKSPACE_ROOT, "quantinsight", "eval", "dataset.json")
RESULTS_PATH = os.path.join(WORKSPACE_ROOT, "quantinsight", "eval", "results.md")

embed_model = SentenceTransformer("BAAI/bge-small-en-v1.5")


def resolve_retrieved_context(citation_uuids: list[Any]) -> str:
    """Fetch exact text content of cited chunks from SQLite database."""
    context_parts = []
    for cid in citation_uuids:
        chunk = get_chunk_by_id(cid)
        if chunk and chunk.content:
            context_parts.append(chunk.content.strip())
            continue

        tbl = get_table_by_chunk_id(cid)
        if tbl:
            caption = tbl.caption or ""
            headers = ", ".join(tbl.headers) if tbl.headers else ""
            rows = " | ".join([", ".join(r) for r in tbl.rows]) if tbl.rows else ""
            context_parts.append(f"Table caption: {caption}. Headers: {headers}. Rows: {rows}")
            continue

        eq = get_equation_by_chunk_id(cid)
        if eq:
            context_parts.append(f"Latex: {eq.latex}. Context: {eq.surrounding_context}")
            continue

    return "\n\n".join(context_parts)


def compute_latex_fidelity(answer: str, ground_truth: str, chunk_type: str) -> float:
    """Compute mathematical & structural fidelity via LaTeX symbol set overlap."""
    latex_regex = re.compile(r"(\\[a-zA-Z]+|[\$\^\_\{\}\(\)\[\]\+\-\=\/\*])")
    ans_tokens = set(latex_regex.findall(answer))
    gt_tokens = set(latex_regex.findall(ground_truth))

    if not gt_tokens:
        # If ground truth doesn't contain explicit LaTeX symbols
        if chunk_type == "equation":
            return 1.0 if ("$" in answer or "\\" in answer) else 0.5
        return 1.0

    overlap = ans_tokens.intersection(gt_tokens)
    return len(overlap) / len(gt_tokens)


CACHE_PATH = os.path.join(WORKSPACE_ROOT, "quantinsight", "eval", "eval_cache.json")


def load_cache() -> dict[int, dict]:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {item["id"]: item for item in data}
        except Exception:
            return {}
    return {}


def save_cache(cache_data: dict[int, dict]):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(list(cache_data.values()), f, indent=2)


async def evaluate_item(idx: int, item: dict, semaphore: asyncio.Semaphore, cache_data: dict[int, dict]) -> dict:
    """Evaluate a single question using the full RAG pipeline & vector embedding metrics."""
    if idx in cache_data:
        print(f"[{idx}] Cached result loaded: '{item['question'][:60]}...'", flush=True)
        return cache_data[idx]

    q = item["question"]
    gt = item["ground_truth"]
    chunk_type = item.get("target_chunk_type", "prose")

    async with semaphore:
        print(f"[{idx}] Evaluating: '{q[:60]}...'", flush=True)
        try:
            resp = await run_agent(query=q, paper_ids=[])
            ans_text = resp.answer or ""

            # Resolve cited text context from SQLite storage
            ctx_text = resolve_retrieved_context(resp.citations)

            # Compute strictly un-mocked vector embeddings
            ans_emb = embed_model.encode(ans_text, convert_to_tensor=True)
            q_emb = embed_model.encode(q, convert_to_tensor=True)
            gt_emb = embed_model.encode(gt, convert_to_tensor=True)

            # 1. Answer Relevancy: cos_sim(generated_answer, question)
            relevancy = float(util.cos_sim(ans_emb, q_emb).item())

            # 2. Faithfulness: cos_sim(generated_answer, retrieved_context)
            if ctx_text:
                ctx_emb = embed_model.encode(ctx_text, convert_to_tensor=True)
                faithfulness = float(util.cos_sim(ans_emb, ctx_emb).item())
                # 3. Context Precision: cos_sim(retrieved_context, ground_truth)
                precision = float(util.cos_sim(ctx_emb, gt_emb).item())
            else:
                # If no cited context was retrieved
                faithfulness = float(util.cos_sim(ans_emb, gt_emb).item()) if "no supporting evidence" in ans_text.lower() else 0.0
                precision = 0.0

            # 4. LaTeX & Structural Fidelity
            latex_fidelity = compute_latex_fidelity(ans_text, gt, chunk_type)

            # Clamp scores strictly into [0.0, 1.0]
            faithfulness = round(max(0.0, min(1.0, faithfulness)), 4)
            precision = round(max(0.0, min(1.0, precision)), 4)
            relevancy = round(max(0.0, min(1.0, relevancy)), 4)
            latex_fidelity = round(max(0.0, min(1.0, latex_fidelity)), 4)

            print(f"  [OK] [{idx}] Done. Faithfulness: {faithfulness}, Precision: {precision}, Relevancy: {relevancy}", flush=True)
            await asyncio.sleep(0.2)

            res = {
                "id": idx,
                "question": q,
                "target_type": chunk_type,
                "faithfulness": faithfulness,
                "context_precision": precision,
                "answer_relevancy": relevancy,
                "latex_fidelity": latex_fidelity,
                "citations_count": len(resp.citations),
                "self_corrected": resp.self_correction_applied,
            }
            cache_data[idx] = res
            save_cache(cache_data)
            return res
        except Exception as e:
            print(f"  [ERROR] Error evaluating question {idx}: {e}", flush=True)
            await asyncio.sleep(0.2)
            err_res = {
                "id": idx,
                "question": q,
                "target_type": chunk_type,
                "faithfulness": 0.0,
                "context_precision": 0.0,
                "answer_relevancy": 0.0,
                "latex_fidelity": 0.0,
                "citations_count": 0,
                "self_corrected": False,
            }
            return err_res


async def execute_evaluation():
    """Run benchmark evaluation suite over dataset.json."""
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Evaluation dataset not found at {DATASET_PATH}")

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cache_data = load_cache()
    print(f"Starting dynamic RAG evaluation of {len(dataset)} benchmark questions (Cached: {len(cache_data)})...")
    semaphore = asyncio.Semaphore(2)

    tasks = [evaluate_item(idx, item, semaphore, cache_data) for idx, item in enumerate(dataset, 1)]
    results = await asyncio.gather(*tasks)

    # Sort results by question ID
    results.sort(key=lambda r: r["id"])

    faithfulness_scores = [r["faithfulness"] for r in results]
    precision_scores = [r["context_precision"] for r in results]
    relevancy_scores = [r["answer_relevancy"] for r in results]

    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
    avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0
    avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0

    prose_prec = [r["context_precision"] for r in results if r["target_type"] == "prose"]
    eq_prec = [r["context_precision"] for r in results if r["target_type"] == "equation"]
    tbl_prec = [r["context_precision"] for r in results if r["target_type"] == "table"]

    avg_prose_prec = sum(prose_prec) / len(prose_prec) if prose_prec else 0.0
    avg_eq_prec = sum(eq_prec) / len(eq_prec) if eq_prec else 0.0
    avg_tbl_prec = sum(tbl_prec) / len(tbl_prec) if tbl_prec else 0.0

    self_corr_count = sum(1 for r in results if r["self_corrected"])
    citation_coverage = sum(1 for r in results if r["citations_count"] > 0) / len(results) if results else 0.0
    avg_latex_fidelity = sum(r["latex_fidelity"] for r in results) / len(results) if results else 0.0

    status = "PASS" if avg_faithfulness >= 0.65 and avg_precision >= 0.65 else "FAIL"

    markdown_report = f"""# ScribeGraph Dynamic Un-Mocked Vector Evaluation Report

- **Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
- **Evaluation Dataset:** {len(dataset)} benchmark questions across landmark papers
- **Evaluation Engine:** SentenceTransformers (`BAAI/bge-small-en-v1.5`) Vector Cosine Similarity
- **Overall Benchmark Status:** `{status}`

## 1. RAGAS Core Generation Metrics

| Metric | Target Threshold | Measured Vector Score | Status | Metric Calculation |
|---|---|---|---|---|
| **Faithfulness** | ≥ 0.65 | **{avg_faithfulness:.4f}** | {"✅ PASS" if avg_faithfulness >= 0.65 else "❌ FAIL"} | `cos_sim(answer, retrieved_context)` |
| **Context Precision** | ≥ 0.65 | **{avg_precision:.4f}** | {"✅ PASS" if avg_precision >= 0.65 else "❌ FAIL"} | `cos_sim(retrieved_context, ground_truth)` |
| **Answer Relevancy** | ≥ 0.80 | **{avg_relevancy:.4f}** | {"✅ PASS" if avg_relevancy >= 0.80 else "❌ FAIL"} | `cos_sim(answer, user_question)` |

## 2. Type-Aware Retrieval Precision Breakdown

| Chunk Type | Evaluated Items | Context Precision Score | Retrieval Domain |
|---|---|---|---|
| **Prose Text** | {len(prose_prec)} Questions | **{avg_prose_prec:.4f}** | Narrative & architectural prose. |
| **LaTeX Equations** | {len(eq_prec)} Questions | **{avg_eq_prec:.4f}** | Mathematical equation & formula units. |
| **Structured Tables** | {len(tbl_prec)} Questions | **{avg_tbl_prec:.4f}** | Performance benchmarks & tabular data. |

## 3. Agentic Reflection & Citation Efficiency

| Reflection / Citation Metric | Measured Score | System Impact |
|---|---|---|
| **Citation Coverage Rate** | **{citation_coverage * 100:.1f}%** | Percentage of answers supported by verified UUID citations. |
| **Self-Correction Trigger Rate** | **{self_corr_count / len(results) * 100:.1f}%** | Percentage of answers refined by Verifier node. |
| **LaTeX Mathematical Fidelity** | **{avg_latex_fidelity:.4f}** | LaTeX mathematical symbol set precision. |

## 4. Question Breakdown Table

| # | Target Type | Faithfulness | Context Precision | Relevancy | Citations | Self-Corrected |
|---|---|---|---|---|---|---|
"""
    for r in results:
        markdown_report += f"| {r['id']} | `{r['target_type']}` | {r['faithfulness']:.2f} | {r['context_precision']:.2f} | {r['answer_relevancy']:.2f} | {r['citations_count']} | {'Yes' if r['self_corrected'] else 'No'} |\n"

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(markdown_report)

    print(f"\nEvaluation complete! Measured Scores -> Faithfulness: {avg_faithfulness:.4f}, Context Precision: {avg_precision:.4f}, Relevancy: {avg_relevancy:.4f}")
    print(f"Report generated at: {RESULTS_PATH}")
    return {
        "status": status,
        "avg_faithfulness": avg_faithfulness,
        "avg_context_precision": avg_precision,
        "avg_answer_relevancy": avg_relevancy,
    }


if __name__ == "__main__":
    asyncio.run(execute_evaluation())
