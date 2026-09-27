import datetime
import uuid

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

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


def init_db() -> None:
    Base.metadata.create_all(engine)
