"""Local storage for the demo product catalog: a JSON metadata file plus a
directory of GLB mesh files (../storage). Stands in for a real database +
object store — swapping either out later means changing only this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
PRODUCTS_FILE = STORAGE_DIR / "products.json"
MODELS_DIR = STORAGE_DIR / "models"


def _load() -> list[dict[str, Any]]:
    if not PRODUCTS_FILE.exists():
        return []
    return json.loads(PRODUCTS_FILE.read_text())


def list_products() -> list[dict[str, Any]]:
    """Metadata only, no model_file path (that's an internal storage detail)."""
    return [{k: v for k, v in p.items() if k != "model_file"} for p in _load()]


def get_product(product_id: str) -> dict[str, Any] | None:
    for p in _load():
        if p["id"] == product_id:
            return {k: v for k, v in p.items() if k != "model_file"}
    return None


def model_path(product_id: str) -> Path | None:
    for p in _load():
        if p["id"] == product_id:
            path = MODELS_DIR / p["model_file"]
            return path if path.exists() else None
    return None
