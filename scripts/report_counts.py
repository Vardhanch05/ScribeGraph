import sqlite3
import os

db_path = os.path.join("data", "quantinsight.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

papers = cursor.execute("SELECT id, title, arxiv_id FROM source_papers").fetchall()
print(f"Total papers found in SQLite: {len(papers)}\n")

for p in papers:
    p_id, title, arxiv_id = p
    prose_count = cursor.execute("SELECT count(id) FROM paper_chunks WHERE paper_id=? AND chunk_type='prose'", (p_id,)).fetchone()[0]
    table_count = cursor.execute("SELECT count(id) FROM table_units WHERE paper_id=?", (p_id,)).fetchone()[0]
    eq_count = cursor.execute("SELECT count(id) FROM equation_units WHERE paper_id=?", (p_id,)).fetchone()[0]
    
    flag = ""
    if eq_count == 0:
        flag += "[FLAG: 0 Equations] "
    if table_count == 0:
        flag += "[FLAG: 0 Tables] "
        
    print(f"Paper ID: {p_id} | ArXiv: {arxiv_id} | Title: {title}")
    print(f"  Prose chunks: {prose_count}")
    print(f"  Table units:  {table_count}")
    print(f"  Eq units:     {eq_count}")
    if flag:
        print(f"  --> {flag}")
    print("-" * 60)
