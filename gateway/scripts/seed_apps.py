"""Seeds demo apps into the database for local testing.

Usage: python -m scripts.seed_apps
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth import create_app
from app.db import init_db

if __name__ == "__main__":
    init_db()

    create_app(
        app_id="support-app",
        raw_key="support-app-demo-key-001",
        role="support",
        allowed_providers=["mock", "workers_ai", "vertex"],
    )
    create_app(
        app_id="analyst-agent",
        raw_key="analyst-agent-demo-key-001",
        role="analyst",
        allowed_providers=["mock", "workers_ai", "vertex", "bedrock", "openai"],
    )

    print("Seeded apps: support-app, analyst-agent")
