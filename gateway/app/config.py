import os

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_AIG_NAME = os.environ.get("CF_AIG_NAME", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
EDGE_SECRET = os.environ.get("EDGE_SECRET", "")

WORKERS_AI_MODEL = os.environ.get("WORKERS_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")

# Bedrock (Claude) — uses the AWS IAM identity from the environment/profile, no API key
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Vertex AI (Gemini) — uses Application Default Credentials locally
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
VERTEX_MODEL_ID = os.environ.get("VERTEX_MODEL_ID", "gemini-2.5-flash")

# OpenAI — via Cloudflare AI Gateway, cheapest tier
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://eacp:eacp@localhost:5432/eacp"
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
