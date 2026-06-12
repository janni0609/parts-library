"""FastAPI application entry point for the parts library."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .routers import categories, parts


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Parts Library", version="0.1.0", lifespan=lifespan)

app.include_router(categories.router)
app.include_router(parts.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
