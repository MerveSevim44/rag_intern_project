import os
import json
import sqlite3
import argparse
from contextlib import closing
from pathlib import Path
try:
    from src.embedder import get_embeddings, EMBED_MODEL
except ImportError:
    from embedder import get_embeddings, EMBED_MODEL
# pyrefly: ignore [missing-import]
import pdfplumber
import docx

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / "rag.db") if (ROOT_DIR / "rag.db").exists() else "rag.db"
DATA_DIR = str(ROOT_DIR / "data") if (ROOT_DIR / "data").exists() else "data"

BATCH_SIZE = 64 #metinlerden embeding oluştururken modelin tek seferde 
                #kaç adet metni işleyeceğini belirtir. GPU belleği arttıkça
                #burası artırılabilir. GPU'su olmayanlar 4-8'de tutabilir.

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
    with closing(connect(db_path)) as conn:
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
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                paragraphs = page_text.split("\n\n")
                for p in paragraphs:
                    cleaned = p.strip()
                    if cleaned:
                        chunks.append((cleaned, f"sayfa {page_num}"))
    return chunks

def _flatten_json(value, path="$"):
    """
    Walks a JSON value and yields (text, path) leaves.

    Dicts/lists are descended into so each leaf keeps a JSONPath-like trail
    ($.users[0].name), which becomes the chunk's page_info and lets an answer
    point back at the exact field it came from.
    """
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from _flatten_json(sub, f"{path}.{key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            yield from _flatten_json(sub, f"{path}[{i}]")
    else:
        if value is None:
            return
        text = str(value).strip()
        if text:
            yield text, path


# A record rendered up to this many characters stays a single chunk; larger
# records fall back to one chunk per leaf field.
MAX_RECORD_CHARS = 3000


def _roots_from_object(data: dict) -> list[tuple[object, str]]:
    """
    Turns a top-level JSON object into (record, path) roots.

    Datasets often wrap their records in a container object, e.g.
    {"datasetName": ..., "profiles": [ ... 728 records ... ]}. In that case the
    items of the dominant list become the records, so each profile is one chunk
    instead of the whole file collapsing into a single oversized record.
    
    Metadata sections like 'fieldGuide', 'safetyAndDataQuality', 'statistics'
    are kept as individual coherent meta-records rather than being fragmented.
    """
    best_key, best_len = None, 0
    for key, value in data.items():
        if isinstance(value, list) and len(value) > best_len and all(
            isinstance(item, (dict, list)) for item in value
        ):
            best_key, best_len = key, len(value)

    if best_key is None or best_len < 2:
        return [(data, "$")]

    roots = [
        (item, f"$.{best_key}[{i}]") for i, item in enumerate(data[best_key])
    ]
    
    # Meta bölümlerini mantıksal ve bütünsel kökler olarak ekle
    remaining = {}
    for k, v in data.items():
        if k == best_key:
            continue
        if isinstance(v, (dict, list)):
            roots.append((v, f"$.{k}"))
        else:
            remaining[k] = v

    if remaining:
        roots.append((remaining, "$.metadata"))

    return roots


def extract_chunks_from_json(file_path: Path) -> list[tuple[str, str]]:
    """
    Reads a .json (or .jsonl) file and turns it into (chunk_text, path_info).

    Records (dicts / list items) are kept together as one chunk when they are
    small enough to read as a unit, so related fields stay in the same
    embedding instead of being scattered across one-line chunks.
    """
    raw = file_path.read_text(encoding="utf-8")

    if file_path.suffix.lower() == ".jsonl":
        records = []
        for line_num, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append((json.loads(line), f"satır {line_num}"))
            except json.JSONDecodeError:
                continue
        roots = records
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path.name}: {e}")
        if isinstance(data, list):
            roots = [(item, f"$[{i}]") for i, item in enumerate(data)]
        else:
            roots = _roots_from_object(data)

    chunks = []
    for root, root_path in roots:
        leaves = list(_flatten_json(root, root_path))
        if not leaves:
            continue
        # Render the whole record as one chunk if it is compact; otherwise fall
        # back to one chunk per leaf so no single chunk dwarfs the others.
        # Field paths are rendered relative to the record so the repeated root
        # prefix does not dominate the chunk text (or its size budget).
        prefix = len(root_path) + 1
        record_text = "\n".join(f"{p[prefix:] or p}: {t}" for t, p in leaves)
        if len(record_text) <= MAX_RECORD_CHARS:
            chunks.append((record_text, root_path))
        else:
            for text, leaf_path in leaves:
                chunks.append((f"{leaf_path}: {text}", leaf_path))
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
    if ext not in {".txt", ".pdf", ".docx", ".json", ".jsonl"}:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .txt, .pdf, .docx, .json, .jsonl")

    # Extract chunks based on file type
    if ext == ".txt":
        chunks = extract_chunks_from_txt(file_path)
    elif ext == ".pdf":
        chunks = extract_chunks_from_pdf(file_path)
    elif ext == ".docx":
        chunks = extract_chunks_from_docx(file_path)
    elif ext in {".json", ".jsonl"}:
        chunks = extract_chunks_from_json(file_path)

    if not chunks:
        raise ValueError(f"No text could be extracted from {file_path.name}")

    source_name = f"data/{file_path.name}"

    # chunks is [(text, page_info), ...]
    texts = [c[0] for c in chunks]
    page_infos = [c[1] for c in chunks]

    # Embeddings are generated BEFORE the database is touched. Embedding a large
    # file takes tens of seconds; doing it inside the write transaction would hold
    # SQLite's write lock that whole time and make every other query fail with
    # "database is locked".
    embeddings = get_embeddings(texts, model=model, batch_size=batch_size, keep_alive="5m")

    data_to_insert = [
        (source_name, text, json.dumps(embedding), page_info)
        for text, page_info, embedding in zip(texts, page_infos, embeddings)
    ]

    with closing(connect(db_path)) as conn:
        cursor = conn.cursor()

        # Delete old chunks for this source (re-ingest), then insert the new ones
        # in the same short transaction.
        cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"Deleted {deleted} old chunks for {source_name}.")

        cursor.executemany(
            "INSERT INTO chunks (source, content, embedding, page_info) VALUES (?, ?, ?, ?)",
            data_to_insert
        )
        conn.commit()

    # Retrieval cache'ini temizle — yeni chunk'lar bir sonraki sorguda görünsün.
    try:
        from src.retrieval import invalidate_cache
    except ImportError:
        from retrieval import invalidate_cache
    invalidate_cache()

    # İngest tamamlandı — embedding modelini bellekten manuel olarak kaldır.
    # Batch'ler sırasında keep_alive="5m" ile sıcak tutuluyordu; artık gerek yok.
    try:
        import ollama as _ollama
        _ollama.embed(model=model, input="", keep_alive="0")
        print(f"Embedding modeli ({model}) bellekten kaldırıldı.")
    except Exception as e:
        print(f"Model unload uyarısı: {e}")

    return len(texts)


def list_ingested_sources(db_path=DB_PATH):
    """
    Returns a list of ingested document sources with chunk counts.

    Returns:
        list[dict]: Each dict has 'source' (str) and 'chunk_count' (int).
    """
    try:
        with closing(connect(db_path)) as conn:
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
    with closing(connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
        deleted = cursor.rowcount
        conn.commit()

    # Retrieval cache'ini temizle — silinen chunk'lar arama sonuçlarında kalmasın.
    try:
        from src.retrieval import invalidate_cache
    except ImportError:
        from retrieval import invalidate_cache
    invalidate_cache()

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
    supported_extensions = {".txt", ".pdf", ".docx", ".json", ".jsonl"}
    files = [f for f in data_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]

    if not files:
        print(f"No supported files (.txt, .pdf, .docx, .json, .jsonl) found in {data_dir}.")
        return

    print(f"Found {len(files)} files to check for ingestion.")

    with closing(connect(db_path)) as conn:
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
                elif file_path.suffix.lower() in {".json", ".jsonl"}:
                    chunks = extract_chunks_from_json(file_path)
                else:
                    continue

                if not chunks:
                    print(f"No text extracted from {file_path.name}. Skipping.")
                    continue

                print(f"Extracted {len(chunks)} chunks.")

                # Check if already ingested
                cursor.execute("SELECT 1 FROM chunks WHERE source = ? LIMIT 1", (source_name,))
                already_ingested = cursor.fetchone() is not None
                if already_ingested and not force:
                    print(f"Already ingested. Skipping (use --force to re-ingest).")
                    continue

                # chunks artık [(text, page_info), ...] formatında
                texts = [c[0] for c in chunks]
                page_infos = [c[1] for c in chunks]

                # 3. Generate embeddings in batches
                print(f"Generating embeddings for {len(texts)} chunks (batch size: {batch_size})...")
                embeddings = get_embeddings(texts, model=model, batch_size=batch_size, keep_alive="5m")

                # 4. Prepare data for batch insertion
                data_to_insert = []
                for text, page_info, embedding in zip(texts, page_infos, embeddings):
                    embedding_json = json.dumps(embedding)
                    data_to_insert.append((source_name, text, embedding_json, page_info))

                # 5. Delete + insert in one short transaction. The DELETE is kept
                #    here (not before the embedding step) so the write lock is
                #    held for milliseconds instead of the whole embedding run.
                if already_ingested:
                    cursor.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
                    print(f"Re-ingesting: removed {cursor.rowcount} old chunks.")

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

    # Tüm dosyalar işlendi — embedding modelini bellekten manuel olarak kaldır.
    try:
        import ollama as _ollama
        _ollama.embed(model=model, input="", keep_alive="0")
        print(f"\nEmbedding modeli ({model}) bellekten kaldırıldı.")
    except Exception as e:
        print(f"\nModel unload uyarısı: {e}")

    print("\nIngestion process finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest TXT, PDF, DOCX and JSON documents with vector embeddings into SQLite.")
    parser.add_argument("--data_dir", type=str, default=DATA_DIR, help="Directory containing documents.")
    parser.add_argument("--db_path", type=str, default=DB_PATH, help="Path to SQLite database.")
    parser.add_argument("--model", type=str, default=EMBED_MODEL, help="Embedding model name.")
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE, help="Batch size for generating embeddings.")
    parser.add_argument("--force", action="store_true", help="Re-ingest files that are already in the database.")

    args = parser.parse_args()
    ingest_files(data_dir=args.data_dir, db_path=args.db_path, model=args.model,
                 batch_size=args.batch_size, force=args.force)
