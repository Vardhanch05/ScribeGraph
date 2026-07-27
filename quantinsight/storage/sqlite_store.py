import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine, select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from quantinsight.schemas.models import (
    ChunkType,
    Citation,
    CitedSummary,
    EquationUnit,
    PaperChunk,
    SourcePaper,
    TableUnit,
)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_DIR = os.path.join(WORKSPACE_ROOT, "data")
DB_FILE = os.path.join(DB_DIR, "quantinsight.db")

# Create data directory if it doesn't exist
os.makedirs(DB_DIR, exist_ok=True)

# SQLite engine configuration (enabling foreign key constraints on connection)
sqlite_url = f"sqlite:///{DB_FILE}"
engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False}
)

# SQLModel DB Models
class SourcePaperDb(SQLModel, table=True):
    __tablename__ = "source_papers"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    arxiv_id: str | None = Field(default=None, index=True, unique=True)
    title: str
    authors: list[str] = Field(sa_column=Column(JSON))
    source_url: str | None = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_markdown_path: str
    page_count: int

class PaperChunkDb(SQLModel, table=True):
    __tablename__ = "paper_chunks"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="source_papers.id", index=True, ondelete="CASCADE")
    chunk_type: str = Field(index=True)
    content: str
    page_number: int
    section_title: str | None = None
    order_index: int
    embedding_id: str | None = None

class TableUnitDb(SQLModel, table=True):
    __tablename__ = "table_units"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="source_papers.id", index=True, ondelete="CASCADE")
    chunk_id: UUID = Field(foreign_key="paper_chunks.id", index=True, ondelete="CASCADE")
    caption: str | None = None
    headers: list[str] = Field(sa_column=Column(JSON))
    rows: list[list[str]] = Field(sa_column=Column(JSON))
    page_number: int

class EquationUnitDb(SQLModel, table=True):
    __tablename__ = "equation_units"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="source_papers.id", index=True, ondelete="CASCADE")
    chunk_id: UUID = Field(foreign_key="paper_chunks.id", index=True, ondelete="CASCADE")
    latex: str
    surrounding_context: str
    equation_label: str | None = Field(default=None, index=True)
    page_number: int

class CitationDb(SQLModel, table=True):
    __tablename__ = "citations"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="source_papers.id", index=True, ondelete="CASCADE")
    cited_text: str
    cited_work_raw: str
    resolved_arxiv_id: str | None = None

class CitedSummaryDb(SQLModel, table=True):
    __tablename__ = "cited_summaries"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="source_papers.id", index=True, ondelete="CASCADE")
    summary: str
    key_claims: list[str] = Field(sa_column=Column(JSON))
    supporting_chunk_ids: list[UUID] = Field(sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_used: str


# Database initialization
def init_db() -> None:
    """Initialize the SQLite database, creating all tables."""
    # Enable foreign keys on SQLite connection
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        
    SQLModel.metadata.create_all(engine)


# Database operation helpers wrapped in Tenacity retries for robustness
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def save_paper_metadata(paper: SourcePaper) -> None:
    """Save or update SourcePaper metadata in SQLite."""
    with Session(engine) as session:
        # Check if already exists
        statement = select(SourcePaperDb).where(SourcePaperDb.id == paper.id)
        db_paper = session.exec(statement).first()
        if not db_paper and paper.arxiv_id:
            # Check by arxiv_id as well
            statement_arxiv = select(SourcePaperDb).where(SourcePaperDb.arxiv_id == paper.arxiv_id)
            db_paper = session.exec(statement_arxiv).first()
            
        if db_paper:
            # Update fields in-place
            db_paper.title = paper.title
            db_paper.authors = paper.authors
            db_paper.source_url = paper.source_url
            db_paper.raw_markdown_path = paper.raw_markdown_path
            db_paper.page_count = paper.page_count
            db_paper.ingested_at = paper.ingested_at
            session.add(db_paper)
        else:
            db_paper = SourcePaperDb(
                id=paper.id,
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=paper.authors,
                source_url=paper.source_url,
                ingested_at=paper.ingested_at,
                raw_markdown_path=paper.raw_markdown_path,
                page_count=paper.page_count
            )
            session.add(db_paper)
        session.commit()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def clean_paper_child_records(paper_id: UUID) -> None:
    """Delete all chunks, tables, equations, citations, and summaries for a paper."""
    with Session(engine) as session:
        # Delete related CitedSummaryDb
        summaries = session.exec(select(CitedSummaryDb).where(CitedSummaryDb.paper_id == paper_id)).all()
        for s in summaries:
            session.delete(s)
            
        # Delete related Citations
        citations = session.exec(select(CitationDb).where(CitationDb.paper_id == paper_id)).all()
        for c in citations:
            session.delete(c)
            
        # Delete related TableUnits
        tables = session.exec(select(TableUnitDb).where(TableUnitDb.paper_id == paper_id)).all()
        for t in tables:
            session.delete(t)
            
        # Delete related EquationUnits
        equations = session.exec(select(EquationUnitDb).where(EquationUnitDb.paper_id == paper_id)).all()
        for eq in equations:
            session.delete(eq)
            
        # Delete related PaperChunks
        chunks = session.exec(select(PaperChunkDb).where(PaperChunkDb.paper_id == paper_id)).all()
        for ch in chunks:
            session.delete(ch)
            
        session.commit()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def save_paper_elements(
    chunks: list[PaperChunk],
    tables: list[TableUnit],
    equations: list[EquationUnit],
    citations: list[Citation],
    summary: CitedSummary
) -> None:
    """Save paper chunks, tables, equations, citations, and summaries to SQLite."""
    with Session(engine) as session:
        # Save PaperChunks
        for chunk in chunks:
            db_chunk = PaperChunkDb(
                id=chunk.id,
                paper_id=chunk.paper_id,
                chunk_type=chunk.chunk_type.value,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                order_index=chunk.order_index,
                embedding_id=chunk.embedding_id
            )
            session.add(db_chunk)
            
        # Flush chunks first to satisfy foreign key constraints for table and equation units
        session.flush()
            
        # Save TableUnits
        for t in tables:
            db_table = TableUnitDb(
                id=t.id,
                paper_id=t.paper_id,
                chunk_id=t.chunk_id,
                caption=t.caption,
                headers=t.headers,
                rows=t.rows,
                page_number=t.page_number
            )
            session.add(db_table)
            
        # Save EquationUnits
        for eq in equations:
            db_eq = EquationUnitDb(
                id=eq.id,
                paper_id=eq.paper_id,
                chunk_id=eq.chunk_id,
                latex=eq.latex,
                surrounding_context=eq.surrounding_context,
                equation_label=eq.equation_label,
                page_number=eq.page_number
            )
            session.add(db_eq)
            
        # Save Citations
        for cit in citations:
            db_cit = CitationDb(
                id=cit.id,
                paper_id=cit.paper_id,
                cited_text=cit.cited_text,
                cited_work_raw=cit.cited_work_raw,
                resolved_arxiv_id=cit.resolved_arxiv_id
            )
            session.add(db_cit)
            
        # Save CitedSummary
        db_sum = CitedSummaryDb(
            id=summary.id,
            paper_id=summary.paper_id,
            summary=summary.summary,
            key_claims=summary.key_claims,
            supporting_chunk_ids=summary.supporting_chunk_ids,
            generated_at=summary.generated_at,
            model_used=summary.model_used
        )
        session.add(db_sum)
        
        session.commit()

# Query operations
def get_paper_by_arxiv_id(arxiv_id: str) -> SourcePaper | None:
    """Retrieve SourcePaper model by arXiv ID from SQLite."""
    with Session(engine) as session:
        statement = select(SourcePaperDb).where(SourcePaperDb.arxiv_id == arxiv_id)
        db_paper = session.exec(statement).first()
        if db_paper:
            return SourcePaper(
                id=db_paper.id,
                arxiv_id=db_paper.arxiv_id,
                title=db_paper.title,
                authors=db_paper.authors,
                source_url=db_paper.source_url,
                ingested_at=db_paper.ingested_at,
                raw_markdown_path=db_paper.raw_markdown_path,
                page_count=db_paper.page_count
            )
    return None

def get_paper_by_id(paper_id: UUID) -> SourcePaper | None:
    """Retrieve SourcePaper model by its UUID from SQLite."""
    with Session(engine) as session:
        statement = select(SourcePaperDb).where(SourcePaperDb.id == paper_id)
        db_paper = session.exec(statement).first()
        if db_paper:
            return SourcePaper(
                id=db_paper.id,
                arxiv_id=db_paper.arxiv_id,
                title=db_paper.title,
                authors=db_paper.authors,
                source_url=db_paper.source_url,
                ingested_at=db_paper.ingested_at,
                raw_markdown_path=db_paper.raw_markdown_path,
                page_count=db_paper.page_count
            )
    return None

def get_paper_chunks(paper_id: UUID) -> list[PaperChunk]:
    """Retrieve list of PaperChunks for a given paper_id."""
    with Session(engine) as session:
        statement = select(PaperChunkDb).where(PaperChunkDb.paper_id == paper_id).order_by(PaperChunkDb.order_index)
        db_chunks = session.exec(statement).all()
        return [
            PaperChunk(
                id=db_ch.id,
                paper_id=db_ch.paper_id,
                chunk_type=ChunkType(db_ch.chunk_type),
                content=db_ch.content,
                page_number=db_ch.page_number,
                section_title=db_ch.section_title,
                order_index=db_ch.order_index,
                embedding_id=db_ch.embedding_id
            )
            for db_ch in db_chunks
        ]

def get_paper_summary(paper_id: UUID) -> CitedSummary | None:
    """Retrieve the CitedSummary for a given paper_id."""
    with Session(engine) as session:
        statement = select(CitedSummaryDb).where(CitedSummaryDb.paper_id == paper_id)
        db_sum = session.exec(statement).first()
        if db_sum:
            return CitedSummary(
                id=db_sum.id,
                paper_id=db_sum.paper_id,
                summary=db_sum.summary,
                key_claims=db_sum.key_claims,
                supporting_chunk_ids=db_sum.supporting_chunk_ids,
                generated_at=db_sum.generated_at,
                model_used=db_sum.model_used
            )
    return None

def list_all_papers() -> list[SourcePaper]:
    """List all ingested papers."""
    with Session(engine) as session:
        db_papers = session.exec(select(SourcePaperDb)).all()
        return [
            SourcePaper(
                id=p.id,
                arxiv_id=p.arxiv_id,
                title=p.title,
                authors=p.authors,
                source_url=p.source_url,
                ingested_at=p.ingested_at,
                raw_markdown_path=p.raw_markdown_path,
                page_count=p.page_count
            )
            for p in db_papers
        ]
