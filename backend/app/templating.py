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
