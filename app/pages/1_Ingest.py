import asyncio
import streamlit as st

from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.storage.sqlite_store import (
    get_equations_by_paper,
    get_paper_by_id,
    get_paper_chunks,
    get_paper_summary,
)

st.set_page_config(
    page_title="Ingest — ScribeGraph",
    page_icon="📥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .page-title {
        font-size: 2rem;
        font-weight: 800;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    .status-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="page-title">📥 Paper Ingestion Pipeline</div>', unsafe_allow_html=True)
st.caption("Ingest arXiv papers by ID or upload raw PDF files to extract structured prose, tables, LaTeX equations, and cited summaries.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Method 1: arXiv Identifier")
    arxiv_input = st.text_input("arXiv Paper ID", placeholder="e.g. 1706.03762 or 1512.03385")
    paper_title = st.text_input("Custom Title (Optional)", placeholder="Attention Is All You Need")
    paper_authors = st.text_input("Authors (Comma separated, Optional)", placeholder="Vaswani et al.")

with col2:
    st.subheader("Method 2: PDF File Upload")
    uploaded_pdf = st.file_uploader("Upload Paper PDF", type=["pdf"])

st.markdown("---")

submit = st.button("🚀 Trigger Ingestion Pipeline", type="primary", use_container_width=True)

if submit:
    if not arxiv_input and not uploaded_pdf:
        st.error("Please provide either an arXiv ID or upload a PDF file.")
    else:
        pdf_bytes = uploaded_pdf.read() if uploaded_pdf else None
        arxiv_id = arxiv_input.strip() if arxiv_input else None
        authors_list = [a.strip() for a in paper_authors.split(",")] if paper_authors else None

        with st.status("Executing ScribeGraph Ingestion Pipeline...", expanded=True) as status_block:
            st.write("📄 Fetching and parsing document structure (LlamaParse)...")
            
            try:
                # Run ingestion in async loop
                paper_id, warnings = asyncio.run(
                    ingest_paper(
                        arxiv_id=arxiv_id,
                        pdf_bytes=pdf_bytes,
                        title=paper_title or None,
                        authors=authors_list,
                    )
                )

                st.write("🧩 Segmenting document into Prose, Tables, and Equations...")
                st.write("🧠 Generating LLM-backed CitedSummary...")
                st.write("⚡ Vectorizing chunks into ChromaDB & persisting to SQLite...")
                
                status_block.update(label="Ingestion Completed Successfully!", state="complete", expanded=False)

                st.success(f"Paper ingested successfully! Assigned Paper ID: `{paper_id}`")

                # Fetch paper details
                paper = get_paper_by_id(paper_id)
                chunks = get_paper_chunks(paper_id)
                eqs = get_equations_by_paper(paper_id)
                summary = get_paper_summary(paper_id)

                if warnings:
                    st.warning("⚠️ Ingestion Warnings Surface:")
                    for w in warnings:
                        st.markdown(f"- {w}")

                st.markdown(
                    f"""
                    <div class="status-card">
                        <h4>{paper.title if paper else 'Ingested Paper'}</h4>
                        <p><b>Chunks Extracted:</b> {len(chunks)} | <b>Equations Parsed:</b> {len(eqs)}</p>
                        <p><b>Summary:</b> {summary.summary if summary else 'N/A'}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.page_link("pages/2_Chat.py", label="💬 Start Chatting with this Paper", icon="💬", use_container_width=True)

            except Exception as exc:
                status_block.update(label=f"Ingestion Failed: {exc}", state="error")
                st.error(f"Error during ingestion: {str(exc)}")
