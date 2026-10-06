from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import admin, approvals, auth, comments, deals, documents, folders, tasks, upload
from app.storage import ensure_bucket

app = FastAPI(title="Lilkis Deal Room API")


@app.on_event("startup")
async def on_startup() -> None:
    ensure_bucket()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,  # required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(deals.router)
app.include_router(folders.router)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(tasks.router)
app.include_router(comments.router)
app.include_router(approvals.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict[str, str]:
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "error",
        "db": db_status,
    }
