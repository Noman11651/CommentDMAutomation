import os
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID", "")
FLOW_START_COOLDOWN_SECONDS = int(os.getenv("FLOW_START_COOLDOWN_SECONDS", "90"))
INBOUND_PAYLOAD_DEDUP_SECONDS = int(os.getenv("INBOUND_PAYLOAD_DEDUP_SECONDS", "15"))

# Comma-separated. Cannot use "*" here while allow_credentials=True (browser rejects that combo).
_DEFAULT_CORS = (
    "https://commentdmautomationfrontend.vercel.app,"
    "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_CORS).split(",") if o.strip()
]
# When the API runs on Vercel, allow any *.vercel.app origin by default so production
# and preview frontends work without extra env. Override with CORS_ORIGIN_REGEX or set
# CORS_ORIGIN_REGEX= to empty in the dashboard to disable.
if "CORS_ORIGIN_REGEX" in os.environ:
    CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None
elif os.environ.get("VERCEL"):
    CORS_ORIGIN_REGEX = r"https://.*\.vercel\.app"
else:
    CORS_ORIGIN_REGEX = None
