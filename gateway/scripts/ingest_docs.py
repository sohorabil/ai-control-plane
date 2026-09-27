"""Chunks docs/ files, embeds each chunk via Vertex, and stores them in the
doc_chunks table for retrieval.

Usage: python -m scripts.ingest_docs [--chunk-size 500]
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import DocChunk, SessionLocal, init_db
from app.providers import vertex

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """Splits on paragraph boundaries first, then packs paragraphs into
    chunks up to chunk_size characters — keeps related sentences together
    rather than cutting mid-thought at a fixed character offset.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) > chunk_size:
            chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current.strip())
    return chunks


async def ingest(chunk_size: int) -> int:
    init_db()
    session = SessionLocal()
    total_chunks = 0

    try:
        session.query(DocChunk).delete()
        session.commit()

        doc_paths = sorted(DOCS_DIR.rglob("*.md"))
        for doc_path in doc_paths:
            rel_path = str(doc_path.relative_to(DOCS_DIR.parent))
            text = doc_path.read_text()
            chunks = chunk_text(text, chunk_size)

            embeddings = await vertex.embed(chunks)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                session.add(
                    DocChunk(
                        source_path=rel_path,
                        chunk_index=i,
                        content=chunk,
                        embedding=embedding,
                    )
                )
                total_chunks += 1

            print(f"Ingested {rel_path}: {len(chunks)} chunk(s)")

        session.commit()
    finally:
        session.close()

    return total_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()

    count = asyncio.run(ingest(args.chunk_size))
    print(f"\nTotal chunks ingested: {count}")
