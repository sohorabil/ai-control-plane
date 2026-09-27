from sqlalchemy import text

from app.db import SessionLocal
from app.providers import vertex


async def vector_search(query: str, top_k: int = 3) -> list[dict]:
    """Pure semantic search: embed the query, find nearest chunks by cosine
    distance.
    """
    [query_embedding] = await vertex.embed([query])
    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT source_path, chunk_index, content, "
                "1 - (embedding <=> (:q)::vector) AS score "
                "FROM doc_chunks ORDER BY embedding <=> (:q)::vector LIMIT :k"
            ),
            {"q": str(query_embedding), "k": top_k},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


async def keyword_search(query: str, top_k: int = 3) -> list[dict]:
    """Pure keyword search via Postgres full-text search."""
    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT source_path, chunk_index, content, "
                "ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)) AS score "
                "FROM doc_chunks "
                "WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :q) "
                "ORDER BY score DESC LIMIT :k"
            ),
            {"q": query, "k": top_k},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


async def hybrid_search(query: str, top_k: int = 3) -> list[dict]:
    """Combines vector and keyword search results, merged by a simple
    reciprocal-rank fusion: a chunk that ranks well in EITHER search gets
    boosted, rewarding chunks found by both.
    """
    vector_results = await vector_search(query, top_k=top_k * 2)
    keyword_results = await keyword_search(query, top_k=top_k * 2)

    def chunk_key(r):
        return (r["source_path"], r["chunk_index"])

    scores: dict[tuple, float] = {}
    chunks_by_key: dict[tuple, dict] = {}

    for rank, r in enumerate(vector_results):
        key = chunk_key(r)
        scores[key] = scores.get(key, 0) + 1 / (rank + 60)
        chunks_by_key[key] = r

    for rank, r in enumerate(keyword_results):
        key = chunk_key(r)
        scores[key] = scores.get(key, 0) + 1 / (rank + 60)
        chunks_by_key[key] = r

    ranked_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [{**chunks_by_key[k], "score": scores[k]} for k in ranked_keys[:top_k]]


async def rerank(query: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    """Uses a chat model to re-score each candidate's relevance to the query
    on a 0-10 scale, then re-sorts. A real cross-encoder reranker model would
    be faster/cheaper, but this proves out whether reranking improves order
    at all before investing in a dedicated model.
    """
    scored = []
    for candidate in candidates:
        judge_prompt = (
            f"Query: {query}\n\nDocument excerpt: {candidate['content']}\n\n"
            f"On a scale of 0-10, how relevant is this excerpt to answering "
            f"the query? Reply with ONLY the number."
        )
        result = await vertex.chat(judge_prompt)
        try:
            score = float(result.answer.strip().split()[0])
        except (ValueError, IndexError):
            score = 0.0
        scored.append({**candidate, "rerank_score": score})

    scored.sort(key=lambda r: r["rerank_score"], reverse=True)
    return scored[:top_k]
