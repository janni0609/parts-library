"""FastAPI application entry point for the parts library."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import categories, categories_ui, import_ui, parts, parts_forms, ui
from .templating import STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Parts Library", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(categories.router)
app.include_router(parts.router)
app.include_router(ui.router)
app.include_router(parts_forms.router)
app.include_router(categories_ui.router)
app.include_router(import_ui.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
