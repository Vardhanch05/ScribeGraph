import re
from uuid import UUID, uuid4

from quantinsight.schemas.models import ChunkType, EquationUnit, PaperChunk, TableUnit


def extract_equation_label(latex: str) -> str | None:
    """
    Extract equation label like \\label{eq:foo} or a trailing number like (1).
    """
    # Look for \label{...}
    label_match = re.search(r'\\label\{([^}]+)\}', latex)
    if label_match:
        return label_match.group(1)
    # Look for trailing equation numbers in parentheses, e.g. (1) or (2.3)
    trailing_match = re.search(r'\(\d+(?:\.\d+)*\)\s*$', latex.strip())
    if trailing_match:
        return trailing_match.group(0)
    return None

def split_table_row(line: str) -> list[str]:
    """
    Split a table row by pipe (|) delimiter, stripping cell content
    and handling outer pipes.
    """
    parts = line.strip().split("|")
    if len(parts) >= 2 and parts[0] == "" and parts[-1] == "":
        return [p.strip() for p in parts[1:-1]]
    return [p.strip() for p in parts]

def is_table_separator(line: str) -> bool:
    """
    Check if a line is a markdown table separator (e.g. |---| or :---:).
    """
    line_stripped = line.strip()
    if (not line_stripped.startswith("|") or not line_stripped.endswith("|")) and "|" not in line_stripped:
        return False
    return bool(re.match(r'^[\s|:\-]+$', line_stripped))

def segment_markdown(
    raw_markdown: str, 
    paper_id: UUID
) -> tuple[list[PaperChunk], list[TableUnit], list[EquationUnit], list[str]]:
    """
    Segment raw markdown into prose chunks, table units, and equation units.
    
    Args:
        raw_markdown: The markdown content returned by LlamaParse.
        paper_id: The UUID of the paper being processed.
        
    Returns:
        Tuple containing:
            - List of PaperChunk objects.
            - List of TableUnit objects.
            - List of EquationUnit objects.
            - List of warning strings (low-confidence extraction flags).
    """
    chunks: list[PaperChunk] = []
    tables: list[TableUnit] = []
    equations: list[EquationUnit] = []
    warnings: list[str] = []
    
    # Split raw markdown by page breaks
    pages = re.split(r'\n---\n|\n--- Page Break ---\n|\f', raw_markdown)
    
    order_index = 0
    
    for page_idx, page_content in enumerate(pages, start=1):
        lines = page_content.splitlines()
        num_lines = len(lines)
        i = 0
        
        while i < num_lines:
            line = lines[i]
            line_strip = line.strip()
            
            if not line_strip:
                i += 1
                continue
                
            # 1. Detect Block Equation
            is_eq_start = False
            eq_end_pattern = None
            
            if line_strip.startswith("$$"):
                is_eq_start = True
                eq_end_pattern = r'\$\$'
            elif line_strip.startswith(r"\["):
                is_eq_start = True
                eq_end_pattern = r'\\\]'
            elif line_strip.startswith(r"\begin{equation}"):
                is_eq_start = True
                eq_end_pattern = r'\\end\{equation\}'
            elif line_strip.startswith(r"\begin{align}"):
                is_eq_start = True
                eq_end_pattern = r'\\end\{align\}'
                
            if is_eq_start and eq_end_pattern:
                eq_lines = [line]
                start_line_num = i
                
                # Check if closed on the same line
                if line_strip.startswith("$$") and len(line_strip) > 2 and line_strip[2:].endswith("$$"):
                    i += 1
                else:
                    i += 1
                    closed = False
                    while i < num_lines:
                        eq_lines.append(lines[i])
                        if re.search(eq_end_pattern, lines[i]):
                            closed = True
                            i += 1
                            break
                        i += 1
                    if not closed:
                        warnings.append(f"Equation starting on page {page_idx} line {start_line_num} was not closed.")
                
                latex_content = "\n".join(eq_lines)
                
                # Construct surrounding context: up to 2 lines before and after
                context_before = [lines[k] for k in range(max(0, start_line_num - 2), start_line_num)]
                context_after = [lines[k] for k in range(i, min(num_lines, i + 2))]
                surrounding_context = "\n".join(context_before + ["[EQUATION]"] + context_after)
                
                label = extract_equation_label(latex_content)
                chunk_id = uuid4()
                
                chunks.append(PaperChunk(
                    id=chunk_id,
                    paper_id=paper_id,
                    chunk_type=ChunkType.EQUATION,
                    content=latex_content,
                    page_number=page_idx,
                    order_index=order_index,
                ))
                equations.append(EquationUnit(
                    id=uuid4(),
                    paper_id=paper_id,
                    chunk_id=chunk_id,
                    latex=latex_content,
                    surrounding_context=surrounding_context,
                    equation_label=label,
                    page_number=page_idx,
                ))
                order_index += 1
                continue
                
            # 2. Detect Markdown Table
            is_table_start = False
            if "|" in line_strip and i + 1 < num_lines:
                next_line = lines[i+1].strip()
                if is_table_separator(next_line):
                    is_table_start = True
                    
            if is_table_start:
                table_lines = [line, lines[i+1]]
                start_line_num = i
                i += 2
                while i < num_lines and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                    
                headers = split_table_row(table_lines[0])
                rows = []
                
                for r_idx, row_line in enumerate(table_lines[2:], start=1):
                    row = split_table_row(row_line)
                    if len(row) != len(headers):
                        warnings.append(
                            f"Low-confidence table extraction on page {page_idx}: row {r_idx} has {len(row)} columns, expected {len(headers)}."
                        )
                        # Pad or truncate row to prevent Pydantic schema validation failures
                        if len(row) < len(headers):
                            row.extend([""] * (len(headers) - len(row)))
                        else:
                            row = row[:len(headers)]
                    rows.append(row)
                    
                table_content = "\n".join(table_lines)
                
                # Look for captions immediately before table
                caption = None
                if start_line_num > 0:
                    prev_line = lines[start_line_num - 1].strip()
                    if prev_line.lower().startswith("table ") or prev_line.lower().startswith("tab. "):
                        caption = prev_line
                
                chunk_id = uuid4()
                chunks.append(PaperChunk(
                    id=chunk_id,
                    paper_id=paper_id,
                    chunk_type=ChunkType.TABLE,
                    content=table_content,
                    page_number=page_idx,
                    order_index=order_index,
                ))
                tables.append(TableUnit(
                    id=uuid4(),
                    paper_id=paper_id,
                    chunk_id=chunk_id,
                    caption=caption,
                    headers=headers,
                    rows=rows,
                    page_number=page_idx,
                ))
                order_index += 1
                continue
                
            # 3. Detect Figure Caption or Prose Block
            prose_lines = [line]
            start_line_num = i
            i += 1
            
            while i < num_lines:
                next_line = lines[i]
                next_line_strip = next_line.strip()
                if not next_line_strip:
                    break
                # Check for new block types
                if (next_line_strip.startswith(("$$", r"\[", r"\begin{equation}", r"\begin{align}"))):
                    break
                if "|" in next_line_strip and i + 1 < num_lines and is_table_separator(lines[i+1]):
                    break
                prose_lines.append(next_line)
                i += 1
                
            prose_content = "\n".join(prose_lines).strip()
            if prose_content:
                chunk_type = ChunkType.PROSE
                if prose_content.lower().startswith("figure ") or prose_content.lower().startswith("fig. "):
                    chunk_type = ChunkType.FIGURE_CAPTION
                    
                chunks.append(PaperChunk(
                    id=uuid4(),
                    paper_id=paper_id,
                    chunk_type=chunk_type,
                    content=prose_content,
                    page_number=page_idx,
                    order_index=order_index,
                ))
                order_index += 1
                
    return chunks, tables, equations, warnings
