from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from routers import webhook, admin

app = FastAPI(title="Instagram Comment-to-DM Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {"status": "ok", "service": "Instagram Comment-to-DM Automation"}

@app.get("/health")
def health():
    return {"status": "healthy"}
