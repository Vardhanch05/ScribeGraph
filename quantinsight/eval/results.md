# ScribeGraph Dynamic Un-Mocked Vector Evaluation Report

- **Date:** 2026-08-12 07:03:07 UTC
- **Evaluation Dataset:** 100 benchmark questions across landmark papers
- **Evaluation Engine:** SentenceTransformers (`BAAI/bge-small-en-v1.5`) Vector Cosine Similarity
- **Overall Benchmark Status:** `PASS`

## 1. RAGAS Core Generation Metrics

| Metric | Target Threshold | Measured Vector Score | Status | Metric Calculation |
|---|---|---|---|---|
| **Faithfulness** | ≥ 0.65 | **0.7448** | ✅ PASS | `cos_sim(answer, retrieved_context)` |
| **Context Precision** | ≥ 0.65 | **0.6986** | ✅ PASS | `cos_sim(retrieved_context, ground_truth)` |
| **Answer Relevancy** | ≥ 0.80 | **0.9087** | ✅ PASS | `cos_sim(answer, user_question)` |

## 2. Type-Aware Retrieval Precision Breakdown

| Chunk Type | Evaluated Items | Context Precision Score | Retrieval Domain |
|---|---|---|---|
| **Prose Text** | 53 Questions | **0.7046** | Narrative & architectural prose. |
| **LaTeX Equations** | 31 Questions | **0.6706** | Mathematical equation & formula units. |
| **Structured Tables** | 16 Questions | **0.7331** | Performance benchmarks & tabular data. |

## 3. Agentic Reflection & Citation Efficiency

| Reflection / Citation Metric | Measured Score | System Impact |
|---|---|---|
| **Citation Coverage Rate** | **97.0%** | Percentage of answers supported by verified UUID citations. |
| **Self-Correction Trigger Rate** | **41.0%** | Percentage of answers refined by Verifier node. |
| **LaTeX Mathematical Fidelity** | **0.6322** | LaTeX mathematical symbol set precision. |

## 4. Question Breakdown Table

| # | Target Type | Faithfulness | Context Precision | Relevancy | Citations | Self-Corrected |
|---|---|---|---|---|---|---|
| 1 | `prose` | 0.65 | 0.79 | 0.79 | 1 | Yes |
| 2 | `equation` | 0.82 | 0.96 | 0.95 | 1 | No |
| 3 | `table` | 0.74 | 0.68 | 0.93 | 2 | No |
| 4 | `prose` | 0.76 | 0.77 | 0.89 | 1 | Yes |
| 5 | `equation` | 0.78 | 0.59 | 0.92 | 1 | Yes |
| 6 | `prose` | 0.68 | 0.69 | 0.84 | 1 | Yes |
| 7 | `table` | 0.72 | 0.75 | 0.89 | 1 | No |
| 8 | `prose` | 0.89 | 0.89 | 0.93 | 1 | No |
| 9 | `prose` | 0.79 | 0.58 | 0.91 | 1 | No |
| 10 | `table` | 0.89 | 0.78 | 0.89 | 1 | No |
| 11 | `equation` | 0.91 | 0.66 | 0.93 | 2 | Yes |
| 12 | `equation` | 0.78 | 0.66 | 0.91 | 1 | Yes |
| 13 | `prose` | 0.82 | 0.84 | 0.91 | 1 | No |
| 14 | `prose` | 0.00 | 0.00 | 0.92 | 0 | No |
| 15 | `prose` | 0.66 | 0.59 | 0.91 | 1 | No |
| 16 | `equation` | 0.83 | 0.60 | 0.90 | 1 | No |
| 17 | `table` | 0.78 | 0.58 | 0.87 | 1 | No |
| 18 | `prose` | 0.75 | 0.83 | 0.93 | 1 | No |
| 19 | `equation` | 0.94 | 0.91 | 0.90 | 1 | No |
| 20 | `table` | 0.75 | 0.81 | 0.91 | 1 | No |
| 21 | `prose` | 0.69 | 0.72 | 0.90 | 1 | No |
| 22 | `equation` | 0.50 | 0.00 | 0.91 | 0 | No |
| 23 | `table` | 0.69 | 0.62 | 0.90 | 1 | Yes |
| 24 | `prose` | 0.68 | 0.61 | 0.91 | 1 | Yes |
| 25 | `equation` | 0.72 | 0.66 | 0.92 | 1 | No |
| 26 | `equation` | 0.81 | 0.66 | 0.91 | 1 | Yes |
| 27 | `prose` | 0.78 | 0.86 | 0.94 | 1 | Yes |
| 28 | `table` | 0.74 | 0.79 | 0.89 | 1 | Yes |
| 29 | `prose` | 0.93 | 0.78 | 0.89 | 1 | No |
| 30 | `equation` | 0.74 | 0.94 | 0.92 | 1 | Yes |
| 31 | `prose` | 0.65 | 0.59 | 0.92 | 1 | No |
| 32 | `prose` | 0.77 | 0.78 | 0.94 | 1 | No |
| 33 | `equation` | 0.76 | 0.60 | 0.88 | 1 | Yes |
| 34 | `prose` | 0.66 | 0.75 | 0.90 | 1 | Yes |
| 35 | `prose` | 0.78 | 0.69 | 0.93 | 1 | Yes |
| 36 | `table` | 0.71 | 0.75 | 0.90 | 1 | Yes |
| 37 | `prose` | 0.80 | 0.81 | 0.91 | 1 | No |
| 38 | `prose` | 0.75 | 0.65 | 0.89 | 1 | No |
| 39 | `prose` | 0.67 | 0.73 | 0.93 | 1 | No |
| 40 | `prose` | 0.72 | 0.72 | 0.89 | 1 | No |
| 41 | `prose` | 0.71 | 0.67 | 0.95 | 1 | Yes |
| 42 | `equation` | 0.63 | 0.70 | 0.91 | 1 | Yes |
| 43 | `prose` | 0.86 | 0.74 | 0.93 | 2 | No |
| 44 | `prose` | 0.89 | 0.81 | 0.94 | 2 | Yes |
| 45 | `prose` | 0.73 | 0.79 | 0.92 | 1 | Yes |
| 46 | `equation` | 0.79 | 0.72 | 0.93 | 1 | Yes |
| 47 | `prose` | 0.72 | 0.60 | 0.92 | 1 | No |
| 48 | `prose` | 0.73 | 0.62 | 0.93 | 1 | No |
| 49 | `equation` | 0.66 | 0.64 | 0.94 | 1 | No |
| 50 | `prose` | 0.71 | 0.74 | 0.92 | 1 | No |
| 51 | `equation` | 0.68 | 0.59 | 0.94 | 1 | No |
| 52 | `prose` | 0.73 | 0.83 | 0.93 | 1 | Yes |
| 53 | `prose` | 0.94 | 0.73 | 0.92 | 3 | No |
| 54 | `prose` | 0.76 | 0.66 | 0.88 | 1 | Yes |
| 55 | `equation` | 0.72 | 0.75 | 0.91 | 1 | Yes |
| 56 | `prose` | 0.65 | 0.57 | 0.90 | 1 | No |
| 57 | `equation` | 0.72 | 0.75 | 0.91 | 1 | No |
| 58 | `prose` | 0.65 | 0.62 | 0.90 | 1 | No |
| 59 | `equation` | 0.72 | 0.59 | 0.93 | 1 | Yes |
| 60 | `prose` | 0.76 | 0.79 | 0.93 | 1 | No |
| 61 | `equation` | 0.81 | 0.70 | 0.90 | 1 | No |
| 62 | `prose` | 0.73 | 0.75 | 0.94 | 1 | Yes |
| 63 | `prose` | 0.71 | 0.59 | 0.91 | 1 | Yes |
| 64 | `equation` | 0.76 | 0.66 | 0.94 | 1 | Yes |
| 65 | `prose` | 0.75 | 0.71 | 0.89 | 1 | Yes |
| 66 | `prose` | 0.76 | 0.77 | 0.94 | 1 | No |
| 67 | `table` | 0.75 | 0.62 | 0.88 | 1 | No |
| 68 | `prose` | 0.74 | 0.70 | 0.94 | 1 | No |
| 69 | `equation` | 0.81 | 0.77 | 0.96 | 1 | Yes |
| 70 | `prose` | 0.65 | 0.64 | 0.92 | 1 | Yes |
| 71 | `equation` | 0.79 | 0.84 | 0.91 | 1 | Yes |
| 72 | `prose` | 0.68 | 0.68 | 0.94 | 1 | No |
| 73 | `prose` | 0.74 | 0.61 | 0.92 | 1 | No |
| 74 | `prose` | 0.68 | 0.62 | 0.94 | 1 | No |
| 75 | `table` | 0.86 | 0.83 | 0.91 | 3 | No |
| 76 | `equation` | 0.82 | 0.96 | 0.93 | 1 | No |
| 77 | `table` | 0.79 | 0.81 | 0.88 | 1 | Yes |
| 78 | `prose` | 0.68 | 0.77 | 0.87 | 1 | Yes |
| 79 | `equation` | 0.61 | 0.64 | 0.92 | 1 | Yes |
| 80 | `prose` | 0.70 | 0.67 | 0.85 | 1 | Yes |
| 81 | `table` | 0.76 | 0.85 | 0.87 | 1 | Yes |
| 82 | `prose` | 0.89 | 0.89 | 0.93 | 1 | No |
| 83 | `prose` | 0.78 | 0.58 | 0.88 | 1 | Yes |
| 84 | `table` | 0.89 | 0.78 | 0.87 | 1 | No |
| 85 | `equation` | 0.78 | 0.65 | 0.86 | 1 | Yes |
| 86 | `equation` | 0.72 | 0.59 | 0.91 | 1 | Yes |
| 87 | `prose` | 0.82 | 0.84 | 0.89 | 1 | No |
| 88 | `prose` | 0.74 | 0.55 | 0.89 | 1 | No |
| 89 | `prose` | 0.81 | 0.67 | 0.91 | 1 | No |
| 90 | `equation` | 0.70 | 0.70 | 0.89 | 1 | No |
| 91 | `table` | 0.79 | 0.62 | 0.88 | 1 | No |
| 92 | `prose` | 0.92 | 0.89 | 0.88 | 3 | No |
| 93 | `equation` | 0.94 | 0.91 | 0.89 | 1 | No |
| 94 | `table` | 0.85 | 0.77 | 0.95 | 1 | No |
| 95 | `prose` | 0.71 | 0.72 | 0.90 | 1 | No |
| 96 | `equation` | 0.00 | 0.00 | 0.92 | 0 | No |
| 97 | `table` | 0.79 | 0.68 | 0.90 | 1 | No |
| 98 | `prose` | 0.92 | 0.85 | 0.92 | 1 | No |
| 99 | `equation` | 0.88 | 0.77 | 0.89 | 1 | No |
| 100 | `equation` | 0.72 | 0.59 | 0.89 | 1 | Yes |
