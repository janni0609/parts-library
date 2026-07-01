"""Shared Jinja2Templates instance for server-rendered pages."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _trimzeros(value: str) -> str:
    """Trim trailing zeros from a formatted decimal, e.g. '0.0120' -> '0.012'."""
    if "." not in value:
        return value
    return value.rstrip("0").rstrip(".")


templates.env.filters["trimzeros"] = _trimzeros


def _static_url(path: str) -> str:
    """Static URL with an mtime-based ``?v=`` query for cache busting.

    Without this, browsers (notably on the Pi) keep serving a cached
    stylesheet/script after a deploy. Tying the query to the file's mtime means
    the URL changes whenever the file does, forcing a fresh fetch.
    """
    try:
        version = int((STATIC_DIR / path).stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path}?v={version}"


templates.env.globals["static_url"] = _static_url
