from uuid import UUID
import pandas as pd
import streamlit as st

from quantinsight.storage.sqlite_store import (
    get_equations_by_paper,
    get_paper_by_id,
    get_paper_chunks,
    get_paper_summary,
    list_all_papers,
)

st.set_page_config(
    page_title="Paper Explorer — ScribeGraph",
    page_icon="🔍",
    layout="wide",
)

st.markdown(
    """
    <style>
    .explorer-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    .chunk-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="explorer-header">🔍 Paper Explorer & Structured Units</div>', unsafe_allow_html=True)
st.caption("Inspect parsed prose blocks, equations, tables, and claims for any ingested paper.")

papers = list_all_papers()

if not papers:
    st.info("No papers available in the library. Ingest a paper first.")
    st.page_link("pages/1_Ingest.py", label="🚀 Ingest Paper", icon="📥")
    st.stop()

paper_options = {f"{p.title} ({p.arxiv_id or str(p.id)[:8]})": p.id for p in papers}
selected_title = st.selectbox("Select Paper to Explore", options=list(paper_options.keys()))
paper_id = paper_options[selected_title]

paper = get_paper_by_id(paper_id)
summary = get_paper_summary(paper_id)
chunks = get_paper_chunks(paper_id)
eqs = get_equations_by_paper(paper_id)

tab_summary, tab_prose, tab_eq, tab_tables = st.tabs(["📝 Cited Summary", "📄 Prose Chunks", "🧮 Equations", "📊 Tables"])

with tab_summary:
    if summary:
        st.subheader("High-Level Summary")
        st.markdown(summary.summary)
        st.markdown("#### Key Claims & Evidence")
        for claim in summary.key_claims:
            st.markdown(f"- {claim}")
        st.caption(f"Generated with model: `{summary.model_used}` at {summary.generated_at.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.info("No summary generated for this paper.")

with tab_prose:
    st.subheader(f"Prose Chunks ({len(chunks)})")
    for chunk in chunks:
        st.markdown(
            f"""
            <div class="chunk-card">
                <div style="font-size: 0.8rem; color: #818CF8; font-weight: 600;">
                    Chunk ID: {chunk.id} | Page: {chunk.page_number} | Section: {chunk.section_title or 'N/A'}
                </div>
                <div style="margin-top: 6px; color: #E2E8F0; white-space: pre-wrap;">{chunk.content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_eq:
    st.subheader(f"Parsed Equations ({len(eqs)})")
    if not eqs:
        st.info("No LaTeX equations extracted from this paper.")
    else:
        for eq in eqs:
            st.markdown(f"**Label:** `{eq.equation_label or 'Unlabeled'}` | **Page:** {eq.page_number}")
            st.latex(eq.latex)
            st.caption(f"Context: {eq.surrounding_context}")
            st.markdown("---")

with tab_tables:
    st.subheader("Parsed Data Tables")
    from quantinsight.storage.sqlite_store import Session, TableUnitDb, engine, select
    with Session(engine) as session:
        db_tables = session.exec(select(TableUnitDb).where(TableUnitDb.paper_id == paper_id)).all()

    if not db_tables:
        st.info("No structured data tables extracted from this paper.")
    else:
        for tbl in db_tables:
            st.markdown(f"**Caption:** {tbl.caption or 'Table'} | **Page:** {tbl.page_number}")

            headers = tbl.headers or []
            clean_headers = []
            seen = {}
            for idx, h in enumerate(headers):
                h_str = str(h).strip() if h is not None else ""
                if not h_str:
                    h_str = f"Col_{idx+1}"
                if h_str in seen:
                    seen[h_str] += 1
                    h_str = f"{h_str}_{seen[h_str]}"
                else:
                    seen[h_str] = 1
                clean_headers.append(h_str)

            try:
                if clean_headers and tbl.rows and len(clean_headers) == len(tbl.rows[0]):
                    df = pd.DataFrame(tbl.rows, columns=clean_headers)
                elif clean_headers:
                    df = pd.DataFrame(tbl.rows)
                    df.columns = clean_headers[: len(df.columns)]
                else:
                    df = pd.DataFrame(tbl.rows)
                st.dataframe(df, use_container_width=True)
            except Exception:
                if tbl.rows:
                    st.table(tbl.rows)

            st.markdown("---")

