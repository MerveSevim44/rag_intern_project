import os
import json
import sqlite3
import argparse
from pathlib import Path
from embedder import get_embeddings
import pypdf
import docx

DB_PATH = "rag.db"
DATA_DIR = "data"
EMBED_MODEL = "bge-m3"
BATCH_SIZE = 16

# Expected schema for the chunks table: column name -> declared type.
# ensure_schema() reconciles the live table against this map, so adding a new
# column here is enough to migrate existing databases.
CHUNK_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "source": "TEXT",
    "content": "TEXT",
    "embedding": "TEXT",
    "page_info": "TEXT",
}

# Columns that can be added to an existing table via ALTER TABLE
# (the primary key cannot, so it is excluded).
MIGRATABLE_COLUMNS = {k: v for k, v in CHUNK_COLUMNS.items() if k != "id"}


def connect(db_path=DB_PATH):
    """
    Opens a SQLite connection tuned for concurrent access.

    timeout: wait instead of failing instantly with "database is locked" when
             another process holds the write lock.
    WAL:     lets readers (the Streamlit app) work while a writer (ingest) runs.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def ensure_schema(conn):
    """
    Creates the chunks table if missing, then adds any column that is absent.

    Also guards against a malformed table: a missing comma in a CREATE TABLE
    statement makes SQLite silently fold the next column name into the previous
    column's *type* (e.g. "embedding TEXT page_info TEXT" becomes one column
    named `embedding` of type "TEXT page_info TEXT"). Such a table is detected
    by comparing declared types and rebuilt from scratch.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            content TEXT,
            embedding TEXT,
            page_info TEXT
        )
    """)

    info = cursor.execute("PRAGMA table_info(chunks)").fetchall()
    existing = {row[1]: (row[2] or "") for row in info}

    # A declared type containing whitespace beyond a simple type name means the
    # table was created from a malformed statement -> unusable, rebuild it.
    corrupt = any(
        name in MIGRATABLE_COLUMNS and len(decl_type.split()) > 1
        for name, decl_type in existing.items()
    )
    if corrupt:
        print("Malformed chunks table detected (missing comma in schema). Rebuilding...")
        cursor.execute("DROP TABLE chunks")
        cursor.execute("""
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                content TEXT,
                embedding TEXT,
                page_info TEXT
            )
        """)
        existing = {}

    # Add any column introduced after this database was first created.
    for name, decl_type in MIGRATABLE_COLUMNS.items():
        if name not in existing:
            try:
                cursor.execute(f"ALTER TABLE chunks ADD COLUMN {name} {decl_type}")
                print(f"Schema migration: added column '{name}' to chunks.")
            except sqlite3.OperationalError as e:
                # Benign if another process added it first; anything else is a
                # real problem worth surfacing.
                if "duplicate column name" not in str(e).lower():
                    raise

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks (source)")
    conn.commit()


def init_db(db_path=DB_PATH):
    """
    Initializes the database, creating or migrating the chunks table as needed.
    """
    with connect(db_path) as conn:
        ensure_schema(conn)
    print(f"Database initialized: {db_path}")

def extract_chunks_from_txt(file_path: Path) -> list[tuple[str, str]]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    paragraphs = content.split("\n\n")
    result = []
    para_num = 0
    for p in paragraphs:
        cleaned = p.strip()
        if cleaned:
            para_num += 1
            result.append((cleaned, f"paragraf {para_num}"))
    return result

def extract_chunks_from_pdf(file_path: Path) -> list[tuple[str, str]]:
    """
    Reads a PDF file, extracts text page by page, and splits by double newline.
    Returns list of (chunk_text, page_info) tuples.
    """
    chunks = []
    reader = pypdf.PdfReader(file_path)
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        if page_text:
            paragraphs = page_text.split("\n\n")
            for p in paragraphs:
                cleaned = p.strip()
                if cleaned:
                    chunks.append((cleaned, f"sayfa {page_num}"))
    return chunks

def extract_chunks_from_docx(file_path: Path) -> list[tuple[str, str]]:
    document = docx.Document(file_path)
    chunks = []
    current_chunk_lines = []
    block_num = 0

    def flush():
        nonlocal block_num
        if current_chunk_lines:
            block_num += 1
            chunks.append(("\n".join(current_chunk_lines), f"bölüm {block_num}"))

    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            current_chunk_lines.append(text)
        else:
            flush()
            current_chunk_lines.clear()
    flush()

    return chunks

def ingest_single_file(file_path, db_path=DB_PATH, model=EMBED_MODEL, batch_size=BATCH_SIZE):
    """
    Ingests a single file into the SQLite database.
    If the file was previously ingested, its old chunks are replaced.

    Args:
        file_path: Path to the file (str or Path).
        db_path: Path to the SQLite database.
        model: Embedding model name.
        batch_size: Batch size for embedding generation.

    Returns:
        int: Number of chunks ingested.

    Raises:
        ValueError: If file type is not supported or no text could be extracted.
        Exception: If embedding generation or DB insertion fails.
    """
    init_db(db_path)
    file_path = Path(file_path)

    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in {".txt", ".pdf", ".docx"}:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .txt, .pdf, .docx")

    # Extract chunks based on file type
    if ext == ".txt":
        chunks = extract_chunks_from_txt(file_path)
    elif ext == ".pdf":
        chunks = extract_chunks_from_pdf(file_path)
    elif ext == ".docx":
        chunks = extract_chunks_from_docx(file_path)

    if not chunks:
        raise ValueError(f"No text could be extracted from {file_path.name}")

    source_name = f"data/{file_path.name}"

    # chunks is [(text, page_info), ...]
    texts = [c[0] for c in chunks]
    page_infos = [c[1] for c in chunks]

    with connect(db_path) as conn:
        cursor = conn.cursor()

        # Delete old chunks for this source (re-ingest)
        cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"Deleted {deleted} old chunks for {source_name}.")

        # Generate embeddings
        embeddings = get_embeddings(texts, model=model, batch_size=batch_size)

        # Insert new chunks
        data_to_insert = []
        for text, page_info, embedding in zip(texts, page_infos, embeddings):
            embedding_json = json.dumps(embedding)
            data_to_insert.append((source_name, text, embedding_json, page_info))

        cursor.executemany(
            "INSERT INTO chunks (source, content, embedding, page_info) VALUES (?, ?, ?, ?)",
            data_to_insert
        )
        conn.commit()

    return len(texts)


def list_ingested_sources(db_path=DB_PATH):
    """
    Returns a list of ingested document sources with chunk counts.

    Returns:
        list[dict]: Each dict has 'source' (str) and 'chunk_count' (int).
    """
    try:
        with connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source, COUNT(*) as cnt FROM chunks GROUP BY source ORDER BY source"
            )
            rows = cursor.fetchall()
        return [{"source": row[0], "chunk_count": row[1]} for row in rows]
    except Exception:
        return []


def delete_source(source_name, db_path=DB_PATH):
    """
    Deletes all chunks for a given source from the database.

    Args:
        source_name: The source identifier (e.g., 'data/test1.txt').
        db_path: Path to the SQLite database.

    Returns:
        int: Number of chunks deleted.
    """
    with connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
        deleted = cursor.rowcount
        conn.commit()
        return deleted


def ingest_files(data_dir=DATA_DIR, db_path=DB_PATH, model=EMBED_MODEL,
                 batch_size=BATCH_SIZE, force=False):
    """
    Ingests all supported files in data_dir into the SQLite database.

    Files that already have chunks in the database are skipped, so re-running
    this is cheap but will NOT pick up edits to an already-ingested file.
    Pass force=True (CLI: --force) to re-ingest them, replacing their chunks.

    Each file is committed on its own, so a failure part-way through does not
    discard the files that already succeeded.
    """
    init_db(db_path)

    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: {data_dir} directory not found.")
        return

    # Find supported files
    supported_extensions = {".txt", ".pdf", ".docx"}
    files = [f for f in data_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]

    if not files:
        print(f"No supported files (.txt, .pdf, .docx) found in {data_dir}.")
        return

    print(f"Found {len(files)} files to check for ingestion.")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for file_path in files:
            source_name = f"{data_dir}/{file_path.name}"
            print(f"\n--- Processing: {file_path.name} ---")

            try:
                # 1. Extract chunks
                if file_path.suffix.lower() == ".txt":
                    chunks = extract_chunks_from_txt(file_path)
                elif file_path.suffix.lower() == ".pdf":
                    chunks = extract_chunks_from_pdf(file_path)
                elif file_path.suffix.lower() == ".docx":
                    chunks = extract_chunks_from_docx(file_path)
                else:
                    continue

                if not chunks:
                    print(f"No text extracted from {file_path.name}. Skipping.")
                    continue

                print(f"Extracted {len(chunks)} chunks.")

                # Check if already ingested
                cursor.execute("SELECT 1 FROM chunks WHERE source = ? LIMIT 1", (source_name,))
                if cursor.fetchone():
                    if not force:
                        print(f"Already ingested. Skipping (use --force to re-ingest).")
                        continue
                    cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
                    print(f"Re-ingesting: removed {cursor.rowcount} old chunks.")

                # chunks artık [(text, page_info), ...] formatında
                texts = [c[0] for c in chunks]
                page_infos = [c[1] for c in chunks]

                # 3. Generate embeddings in batches
                print(f"Generating embeddings for {len(texts)} chunks (batch size: {batch_size})...")
                embeddings = get_embeddings(texts, model=model, batch_size=batch_size)

                # 4. Prepare data for batch insertion
                data_to_insert = []
                for text, page_info, embedding in zip(texts, page_infos, embeddings):
                    embedding_json = json.dumps(embedding)
                    data_to_insert.append((source_name, text, embedding_json, page_info))

                # 5. Batch insert
                cursor.executemany(
                    "INSERT INTO chunks (source, content, embedding, page_info) VALUES (?, ?, ?, ?)",
                    data_to_insert
                )
                # Commit per file so one bad file cannot discard the good ones.
                conn.commit()
                print(f"Successfully ingested and committed {len(texts)} chunks.")

            except Exception as e:
                print(f"Error processing {file_path.name}: {e}")
                conn.rollback()

    print("\nIngestion process finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest TXT and PDF documents with vector embeddings into SQLite.")
    parser.add_argument("--data_dir", type=str, default=DATA_DIR, help="Directory containing documents.")
    parser.add_argument("--db_path", type=str, default=DB_PATH, help="Path to SQLite database.")
    parser.add_argument("--model", type=str, default=EMBED_MODEL, help="Embedding model name.")
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE, help="Batch size for generating embeddings.")
    parser.add_argument("--force", action="store_true", help="Re-ingest files that are already in the database.")

    args = parser.parse_args()
    ingest_files(data_dir=args.data_dir, db_path=args.db_path, model=args.model,
                 batch_size=args.batch_size, force=args.force)
