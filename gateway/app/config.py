import os

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_AIG_NAME = os.environ.get("CF_AIG_NAME", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
EDGE_SECRET = os.environ.get("EDGE_SECRET", "")

WORKERS_AI_MODEL = os.environ.get("WORKERS_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
