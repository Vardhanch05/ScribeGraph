from uuid import uuid4

from quantinsight.ingestion.segmenter import segment_markdown
from quantinsight.schemas.models import ChunkType


def test_segment_markdown_basic():
    raw_md = """# Introduction
This is a prose paragraph discussing transformers.

--- Page Break ---
## Math and Equations
Here is a block equation:
$$
E = mc^2 \\label{eq:einstein}
$$
And some text in between.
\\[
\\nabla \\times \\mathbf{B} = \\mu_0 \\mathbf{J} + \\mu_0 \\epsilon_0 \\frac{\\partial \\mathbf{E}}{\\partial t}
\\]

--- Page Break ---
## Tables
Table 1: Experimental Results
| Metric | Model A | Model B |
|---|---|---|
| Accuracy | 92.5% | 94.1% |
| F1 Score | 0.912 | 0.935 |

Fig. 1: Architecture Diagram
This is a description of the diagram.
"""
    paper_id = uuid4()
    chunks, tables, equations, warnings = segment_markdown(raw_md, paper_id)

    # Assertions
    assert len(warnings) == 0

    # Check chunks types
    # Expected chunks in order:
    # 0. Prose (Introduction...)
    # 1. Prose (Math and Equations...)
    # 2. Equation (E=mc^2)
    # 3. Prose (And some text in between.)
    # 4. Equation (Maxwell's eq)
    # 5. Prose (Tables...)
    # 6. Table (Metric | Model A...)
    # 7. Figure Caption (Fig. 1...)

    assert len(chunks) == 8

    # Validate order_index and page_number
    for idx, chunk in enumerate(chunks):
        assert chunk.order_index == idx
        assert chunk.paper_id == paper_id

    assert chunks[0].chunk_type == ChunkType.PROSE
    assert chunks[0].page_number == 1
    assert "transformers" in chunks[0].content

    assert chunks[2].chunk_type == ChunkType.EQUATION
    assert chunks[2].page_number == 2

    assert len(equations) == 2
    assert equations[0].equation_label == "eq:einstein"
    assert equations[0].page_number == 2
    assert equations[0].chunk_id == chunks[2].id
    assert "[EQUATION]" in equations[0].surrounding_context

    assert chunks[6].chunk_type == ChunkType.TABLE
    assert chunks[6].page_number == 3

    assert len(tables) == 1
    assert tables[0].caption == "Table 1: Experimental Results"
    assert tables[0].headers == ["Metric", "Model A", "Model B"]
    assert tables[0].rows == [
        ["Accuracy", "92.5%", "94.1%"],
        ["F1 Score", "0.912", "0.935"],
    ]
    assert tables[0].page_number == 3
    assert tables[0].chunk_id == chunks[6].id

    assert chunks[7].chunk_type == ChunkType.FIGURE_CAPTION
    assert chunks[7].page_number == 3
    assert chunks[7].content.startswith("Fig. 1")


def test_segment_markdown_table_warnings():
    raw_md = """# Bad Table
| Header 1 | Header 2 |
|---|---|
| Row 1 Col 1 | Row 1 Col 2 |
| Row 2 Col 1 |
| Row 3 Col 1 | Row 3 Col 2 | Row 3 Col 3 |
"""
    paper_id = uuid4()
    _chunks, tables, _equations, warnings = segment_markdown(raw_md, paper_id)

    # We expect 2 warnings because Row 2 has 1 column, and Row 3 has 3 columns (headers has 2).
    assert len(warnings) == 2
    assert any("row 2 has 1 columns, expected 2" in w for w in warnings)
    assert any("row 3 has 3 columns, expected 2" in w for w in warnings)

    assert len(tables) == 1
    assert tables[0].headers == ["Header 1", "Header 2"]
    # Row 2 should be padded: ["Row 2 Col 1", ""]
    # Row 3 should be truncated: ["Row 3 Col 1", "Row 3 Col 2"]
    assert tables[0].rows == [
        ["Row 1 Col 1", "Row 1 Col 2"],
        ["Row 2 Col 1", ""],
        ["Row 3 Col 1", "Row 3 Col 2"],
    ]
