# ScribeGraph Dynamic Un-Mocked Vector Evaluation Report

- **Date:** 2026-08-12 14:34:48 UTC
- **Evaluation Dataset:** 100 benchmark questions across landmark papers
- **Evaluation Engine:** SentenceTransformers (`BAAI/bge-small-en-v1.5`) Vector Cosine Similarity
- **Overall Benchmark Status:** `FAIL`

## 1. RAGAS Core Generation Metrics

| Metric | Target Threshold | Measured Vector Score | Status | Metric Calculation |
|---|---|---|---|---|
| **Faithfulness** | ≥ 0.65 | **0.7157** | ✅ PASS | `cos_sim(answer, retrieved_context)` |
| **Context Precision** | ≥ 0.65 | **0.6408** | ❌ FAIL | `cos_sim(retrieved_context, ground_truth)` |
| **Answer Relevancy** | ≥ 0.80 | **0.8890** | ✅ PASS | `cos_sim(answer, user_question)` |

## 2. Type-Aware Retrieval Precision Breakdown

| Chunk Type | Evaluated Items | Context Precision Score | Retrieval Domain |
|---|---|---|---|
| **Prose Text** | 53 Questions | **0.6423** | Narrative & architectural prose. |
| **LaTeX Equations** | 31 Questions | **0.6130** | Mathematical equation & formula units. |
| **Structured Tables** | 16 Questions | **0.6898** | Performance benchmarks & tabular data. |

## 3. Agentic Reflection & Citation Efficiency

| Reflection / Citation Metric | Measured Score | System Impact |
|---|---|---|
| **Citation Coverage Rate** | **90.0%** | Percentage of answers supported by verified UUID citations. |
| **Self-Correction Trigger Rate** | **17.0%** | Percentage of answers refined by Verifier node. |
| **LaTeX Mathematical Fidelity** | **0.6186** | LaTeX mathematical symbol set precision. |

## 4. Question Breakdown Table

| # | Target Type | Faithfulness | Context Precision | Relevancy | Citations | Self-Corrected |
|---|---|---|---|---|---|---|
| 1 | `prose` | 0.93 | 0.84 | 0.69 | 2 | Yes |
| 2 | `equation` | 0.82 | 0.96 | 0.95 | 1 | No |
| 3 | `table` | 0.86 | 0.75 | 0.93 | 3 | No |
| 4 | `prose` | 0.36 | 0.00 | 0.42 | 0 | No |
| 5 | `equation` | 0.78 | 0.59 | 0.92 | 1 | Yes |
| 6 | `prose` | 0.76 | 0.86 | 0.94 | 1 | No |
| 7 | `table` | 0.87 | 0.86 | 0.94 | 1 | No |
| 8 | `prose` | 0.74 | 0.84 | 0.88 | 1 | Yes |
| 9 | `prose` | 0.97 | 0.75 | 0.94 | 3 | No |
| 10 | `table` | 0.88 | 0.78 | 0.83 | 1 | No |
| 11 | `equation` | 0.90 | 0.66 | 0.93 | 2 | Yes |
| 12 | `equation` | 0.88 | 0.82 | 0.93 | 2 | Yes |
| 13 | `prose` | 0.91 | 0.81 | 0.91 | 3 | Yes |
| 14 | `prose` | 0.69 | 0.53 | 0.94 | 1 | Yes |
| 15 | `prose` | 0.00 | 0.00 | 0.90 | 0 | No |
| 16 | `equation` | 0.00 | 0.00 | 0.80 | 0 | No |
| 17 | `table` | 0.72 | 0.60 | 0.84 | 1 | No |
| 18 | `prose` | 0.74 | 0.82 | 0.93 | 1 | Yes |
| 19 | `equation` | 0.78 | 0.78 | 0.90 | 1 | Yes |
| 20 | `table` | 0.90 | 0.79 | 0.94 | 1 | No |
| 21 | `prose` | 0.77 | 0.75 | 0.91 | 2 | Yes |
| 22 | `equation` | 0.44 | 0.00 | 0.74 | 0 | No |
| 23 | `table` | 0.90 | 0.75 | 0.92 | 4 | Yes |
| 24 | `prose` | 0.00 | 0.00 | 0.87 | 0 | No |
| 25 | `equation` | 0.68 | 0.69 | 0.91 | 1 | Yes |
| 26 | `equation` | 0.57 | 0.00 | 0.80 | 0 | No |
| 27 | `prose` | 0.78 | 0.86 | 0.94 | 1 | No |
| 28 | `table` | 0.71 | 0.00 | 0.76 | 0 | No |
| 29 | `prose` | 0.82 | 0.81 | 0.89 | 1 | Yes |
| 30 | `equation` | 0.86 | 0.84 | 0.91 | 2 | No |
| 31 | `prose` | 0.59 | 0.50 | 0.91 | 1 | No |
| 32 | `prose` | 0.82 | 0.88 | 0.94 | 1 | No |
| 33 | `equation` | 0.76 | 0.60 | 0.88 | 1 | No |
| 34 | `prose` | 0.56 | 0.66 | 0.90 | 1 | No |
| 35 | `prose` | 0.75 | 0.68 | 0.93 | 1 | No |
| 36 | `table` | 0.69 | 0.57 | 0.91 | 1 | No |
| 37 | `prose` | 0.85 | 0.85 | 0.91 | 1 | No |
| 38 | `prose` | 0.78 | 0.78 | 0.88 | 1 | No |
| 39 | `prose` | 0.76 | 0.77 | 0.93 | 1 | No |
| 40 | `prose` | 0.75 | 0.72 | 0.89 | 1 | No |
| 41 | `prose` | 0.75 | 0.76 | 0.95 | 1 | No |
| 42 | `equation` | 0.78 | 0.71 | 0.91 | 1 | No |
| 43 | `prose` | 0.79 | 0.71 | 0.90 | 1 | No |
| 44 | `prose` | 0.50 | 0.42 | 0.91 | 1 | No |
| 45 | `prose` | 0.85 | 0.80 | 0.92 | 1 | No |
| 46 | `equation` | 0.72 | 0.59 | 0.93 | 1 | No |
| 47 | `prose` | 0.64 | 0.65 | 0.92 | 1 | No |
| 48 | `prose` | 0.63 | 0.47 | 0.93 | 1 | No |
| 49 | `equation` | 0.70 | 0.65 | 0.94 | 1 | No |
| 50 | `prose` | 0.83 | 0.76 | 0.93 | 1 | No |
| 51 | `equation` | 0.82 | 0.66 | 0.93 | 1 | No |
| 52 | `prose` | 0.79 | 0.74 | 0.92 | 1 | No |
| 53 | `prose` | 0.82 | 0.72 | 0.93 | 1 | No |
| 54 | `prose` | 0.76 | 0.66 | 0.88 | 1 | No |
| 55 | `equation` | 0.72 | 0.75 | 0.91 | 1 | No |
| 56 | `prose` | 0.73 | 0.61 | 0.90 | 1 | No |
| 57 | `equation` | 0.60 | 0.71 | 0.91 | 1 | No |
| 58 | `prose` | 0.58 | 0.57 | 0.90 | 1 | No |
| 59 | `equation` | 0.54 | 0.50 | 0.93 | 1 | No |
| 60 | `prose` | 0.72 | 0.80 | 0.93 | 1 | No |
| 61 | `equation` | 0.81 | 0.70 | 0.90 | 1 | No |
| 62 | `prose` | 0.73 | 0.75 | 0.94 | 1 | No |
| 63 | `prose` | 0.71 | 0.59 | 0.91 | 1 | No |
| 64 | `equation` | 0.69 | 0.62 | 0.94 | 1 | No |
| 65 | `prose` | 0.00 | 0.00 | 0.86 | 0 | No |
| 66 | `prose` | 0.76 | 0.77 | 0.94 | 1 | No |
| 67 | `table` | 0.73 | 0.62 | 0.89 | 1 | No |
| 68 | `prose` | 0.53 | 0.40 | 0.94 | 1 | No |
| 69 | `equation` | 0.68 | 0.72 | 0.94 | 1 | No |
| 70 | `prose` | 0.67 | 0.72 | 0.92 | 1 | No |
| 71 | `equation` | 0.71 | 0.00 | 0.77 | 0 | Yes |
| 72 | `prose` | 0.68 | 0.68 | 0.94 | 1 | No |
| 73 | `prose` | 0.78 | 0.68 | 0.92 | 1 | No |
| 74 | `prose` | 0.81 | 0.67 | 0.95 | 2 | Yes |
| 75 | `table` | 0.90 | 0.87 | 0.91 | 2 | Yes |
| 76 | `equation` | 0.82 | 0.96 | 0.93 | 1 | No |
| 77 | `table` | 0.77 | 0.68 | 0.91 | 2 | Yes |
| 78 | `prose` | 0.36 | 0.00 | 0.41 | 0 | No |
| 79 | `equation` | 0.92 | 0.73 | 0.87 | 2 | No |
| 80 | `prose` | 0.94 | 0.82 | 0.79 | 2 | No |
| 81 | `table` | 0.88 | 0.86 | 0.91 | 1 | No |
| 82 | `prose` | 0.69 | 0.64 | 0.85 | 1 | No |
| 83 | `prose` | 0.75 | 0.66 | 0.88 | 1 | No |
| 84 | `table` | 0.73 | 0.81 | 0.87 | 1 | No |
| 85 | `equation` | 0.75 | 0.64 | 0.86 | 1 | No |
| 86 | `equation` | 0.79 | 0.83 | 0.91 | 1 | No |
| 87 | `prose` | 0.82 | 0.84 | 0.89 | 1 | No |
| 88 | `prose` | 0.74 | 0.55 | 0.89 | 1 | No |
| 89 | `prose` | 0.81 | 0.75 | 0.90 | 1 | No |
| 90 | `equation` | 0.70 | 0.70 | 0.89 | 1 | No |
| 91 | `table` | 0.79 | 0.57 | 0.88 | 1 | No |
| 92 | `prose` | 0.72 | 0.77 | 0.89 | 1 | No |
| 93 | `equation` | 0.71 | 0.76 | 0.89 | 1 | No |
| 94 | `table` | 0.74 | 0.81 | 0.88 | 1 | No |
| 95 | `prose` | 0.76 | 0.75 | 0.91 | 1 | No |
| 96 | `equation` | 0.72 | 0.52 | 0.93 | 1 | No |
| 97 | `table` | 0.80 | 0.71 | 0.86 | 1 | No |
| 98 | `prose` | 0.65 | 0.64 | 0.88 | 1 | No |
| 99 | `equation` | 0.73 | 0.71 | 0.88 | 1 | No |
| 100 | `equation` | 0.72 | 0.59 | 0.89 | 1 | No |
