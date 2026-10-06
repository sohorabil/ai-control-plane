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

# Vertex AI (Gemini) — auth method depends on environment, both use the same
# code path (google.auth.default() picks whichever is active):
#   - Local dev: Application Default Credentials, no env var needed
#     (`gcloud auth application-default login`)
#   - On AWS (from Part 9 onward): set GOOGLE_APPLICATION_CREDENTIALS to
#     gateway/wif-credential-config.json — this makes Google's client library
#     fetch AWS role credentials from the EC2/EKS metadata endpoint instead
#     of reading any Google credential file. Only works when actually
#     running on AWS with the eacp-gateway-role IAM role attached; contains
#     no secrets itself (just the WIF trust-chain addresses), safe to commit.
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

# Part 11 — OpenTelemetry. host.docker.internal works both from inside a
# kind pod (reaches the Jaeger container on the host's Docker network) and
# from a plain local `uvicorn` process (reaches Docker Desktop's gateway IP)
# — verified both paths work from this project's actual setup.
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://host.docker.internal:4318"
)
# Lets an environment opt out of tracing entirely when no collector exists
# there at all (e.g. this project's real-EKS demo, which never stood up a
# Jaeger instance — tracing was already proven locally in Part 11). Without
# this, every request pays for a failed export attempt and that failure
# shows up as log noise an on-call engineer (or the Incident Agent) could
# mistake for the actual incident.
TRACING_ENABLED = os.environ.get("TRACING_ENABLED", "true").lower() == "true"

# Part 13 — Incident Agent reads Prometheus the same way (host.docker.internal,
# same cross-network reasoning as Jaeger above).
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://host.docker.internal:9090")

# Part 13 — the Rollback Executor is a sibling Service in the SAME cluster
# namespace, so a plain Kubernetes Service DNS name works here (unlike
# Prometheus/Jaeger, which live outside kind entirely).
ROLLBACK_EXECUTOR_URL = os.environ.get("ROLLBACK_EXECUTOR_URL", "http://rollback-executor:8001")
