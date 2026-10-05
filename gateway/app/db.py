import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, text, Column, String, Integer, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

EMBEDDING_DIM = 768  # Vertex text-embedding-005 output size

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Usage(Base):
    __tablename__ = "usage"

    request_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    fallback = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class App(Base):
    __tablename__ = "apps"

    app_id = Column(String, primary_key=True)          # human-readable name, e.g. "support-app"
    key_hash = Column(String, nullable=False, unique=True)  # sha256 of the real API key
    role = Column(String, nullable=False)               # e.g. "support", "analyst", "admin"
    allowed_providers = Column(JSON, nullable=False)    # e.g. ["workers_ai", "vertex"]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)   # e.g. "pii_redacted", "pii_blocked", "denied_provider", "injection_blocked"
    detail = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Feedback(Base):
    """Part 12's feedback loop: thumbs up/down on a playground or agent
    answer. Never auto-promoted into evals/golden.jsonl — a human reviews
    thumbs-down cases first (see scripts/review_feedback.py), since letting
    one bad vote silently poison the golden set would make it untrustworthy.
    """
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source = Column(String, nullable=False)   # "playground" | "agent" | "rag"
    rating = Column(String, nullable=False)   # "up" | "down"
    reviewed = Column(Boolean, default=False)
    added_to_golden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_path = Column(String, nullable=False)   # e.g. docs/policies/refund_policy.md
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        # Full-text search index for the hybrid search comparison later.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS doc_chunks_fts_idx ON doc_chunks "
                "USING GIN (to_tsvector('english', content))"
            )
        )
        conn.commit()
