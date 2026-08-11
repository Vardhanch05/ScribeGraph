import streamlit as st
from quantinsight.storage.sqlite_store import list_all_papers, get_paper_chunks, get_equations_by_paper
from quantinsight.storage.sqlite_store import init_db

st.set_page_config(
    page_title="ScribeGraph — Agentic Research & Context Engineering",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize DB schema
init_db()

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366F1 0%, #A855F7 50%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #94A3B8;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .metric-val {
        font-size: 2rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .paper-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .paper-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #F1F5F9;
        margin-bottom: 0.4rem;
    }
    .paper-meta {
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 0.8rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(99, 102, 241, 0.15);
        color: #818CF8;
        margin-right: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">⚡ ScribeGraph Research Hub</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Agentic Context Engineering & Self-Correcting Technical Paper Analysis</div>',
    unsafe_allow_html=True,
)

papers = list_all_papers()

# Compute aggregates
total_chunks = 0
total_equations = 0

for p in papers:
    chunks = get_paper_chunks(p.id)
    eqs = get_equations_by_paper(p.id)
    total_chunks += len(chunks)
    total_equations += len(eqs)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{len(papers)}</div><div class="metric-lbl">Ingested Papers</div></div>',
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{total_chunks}</div><div class="metric-lbl">Vector Chunks</div></div>',
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{total_equations}</div><div class="metric-lbl">LaTeX Equations</div></div>',
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">v0.1.0</div><div class="metric-lbl">System Release</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

st.subheader("📚 Paper Knowledge Base")

if not papers:
    st.info("No research papers ingested yet. Click below to add your first arXiv paper or PDF.")
    st.page_link("pages/1_Ingest.py", label="🚀 Go to Ingest Page", icon="📥", use_container_width=True)
else:
    for paper in papers:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(
                f"""
                <div class="paper-card">
                    <div class="paper-title">{paper.title}</div>
                    <div class="paper-meta">Authors: {", ".join(paper.authors)} | arXiv: {paper.arxiv_id or "Local PDF"} | Pages: {paper.page_count}</div>
                    <div>
                        <span class="badge">UUID: {str(paper.id)[:8]}...</span>
                        <span class="badge">Ingested: {paper.ingested_at.strftime("%Y-%m-%d %H:%M")}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("💬 Chat", key=f"chat_{paper.id}", use_container_width=True):
                st.session_state["selected_paper_ids"] = [str(paper.id)]
                st.switch_page("pages/2_Chat.py")
