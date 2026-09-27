import hashlib

from fastapi import HTTPException

from app.db import App, SessionLocal


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_app(app_id: str, raw_key: str, role: str, allowed_providers: list[str]) -> None:
    session = SessionLocal()
    try:
        session.merge(
            App(
                app_id=app_id,
                key_hash=hash_key(raw_key),
                role=role,
                allowed_providers=allowed_providers,
                is_active=True,
            )
        )
        session.commit()
    finally:
        session.close()


def authenticate_app(raw_key: str) -> App:
    """Looks up the app by its key's hash. Raises 401 if no match or inactive."""
    session = SessionLocal()
    try:
        key_hash = hash_key(raw_key)
        app = session.query(App).filter_by(key_hash=key_hash, is_active=True).first()
        if not app:
            raise HTTPException(status_code=401, detail="invalid or inactive app key")
        # Detach from session so caller can use it after session closes.
        session.expunge(app)
        return app
    finally:
        session.close()


def check_provider_allowed(app: App, provider: str) -> None:
    if provider not in app.allowed_providers:
        raise HTTPException(
            status_code=403,
            detail=f"app '{app.app_id}' (role: {app.role}) is not allowed to use provider '{provider}'",
        )
