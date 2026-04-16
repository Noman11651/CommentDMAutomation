import os
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID", "")

# Comma-separated. Cannot use "*" here while allow_credentials=True (browser rejects that combo).
_DEFAULT_CORS = (
    "https://commentdmautomationfrontend.vercel.app,"
    "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_CORS).split(",") if o.strip()
]
# Optional: e.g. https://.*\\.vercel\\.app for preview deployments
_cors_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip()
CORS_ORIGIN_REGEX = _cors_regex or None
