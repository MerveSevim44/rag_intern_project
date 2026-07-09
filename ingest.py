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

def init_db(db_path=DB_PATH):
    """
    Initializes the database and creates the chunks table if it doesn't exist.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                content TEXT,
                embedding TEXT
            )
        """)
        # Create index on source to optimize deletion/filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks (source)")
    print(f"Database initialized: {db_path}")

def extract_chunks_from_txt(file_path: Path) -> list[str]:
    """
    Reads a TXT file and splits it into paragraphs.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    paragraphs = content.split("\n\n")
    return [p.strip() for p in paragraphs if p.strip()]

def extract_chunks_from_pdf(file_path: Path) -> list[str]:
    """
    Reads a PDF file, extracts text page by page, and splits by double newline.
    """
    chunks = []
    reader = pypdf.PdfReader(file_path)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            paragraphs = page_text.split("\n\n")
            for p in paragraphs:
                cleaned = p.strip()
                if cleaned:
                    chunks.append(cleaned)
    return chunks

def extract_chunks_from_docx(file_path: Path) -> list[str]:
    """
    Reads a DOCX file and splits it into chunks by grouping consecutive
    non-empty paragraphs. A blank paragraph acts as a chunk separator.
    """
    document = docx.Document(file_path)
    chunks = []
    current_chunk_lines = []

    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            current_chunk_lines.append(text)
        else:
            # Blank paragraph = chunk boundary
            if current_chunk_lines:
                chunks.append("\n".join(current_chunk_lines))
                current_chunk_lines = []

    # Flush any remaining lines as the last chunk
    if current_chunk_lines:
        chunks.append("\n".join(current_chunk_lines))

    return chunks

def ingest_files(data_dir=DATA_DIR, db_path=DB_PATH, model=EMBED_MODEL, batch_size=BATCH_SIZE):
    """
    Ingests all supported files in data_dir into the SQLite database.
    This process is idempotent (overwrites existing chunks for the same files).
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
                    print(f"Already ingested. Skipping.")
                    continue

                # 3. Generate embeddings in batches
                print(f"Generating embeddings for {len(chunks)} chunks (batch size: {batch_size})...")
                embeddings = get_embeddings(chunks, model=model, batch_size=batch_size)

                # 4. Prepare data for batch insertion
                data_to_insert = []
                for chunk, embedding in zip(chunks, embeddings):
                    embedding_json = json.dumps(embedding)
                    data_to_insert.append((source_name, chunk, embedding_json))

                # 5. Batch insert
                cursor.executemany(
                    "INSERT INTO chunks (source, content, embedding) VALUES (?, ?, ?)",
                    data_to_insert
                )
                print(f"Successfully ingested and committed {len(chunks)} chunks.")

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
    
    args = parser.parse_args()
    ingest_files(data_dir=args.data_dir, db_path=args.db_path, model=args.model, batch_size=args.batch_size)
