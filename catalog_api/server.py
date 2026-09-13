"""Retailer-facing catalog API.

Serves the small local library of 3D product models — produced upstream by
the core image->3D pipeline (see the sibling image_reconstruction project:
detectors.py -> fal_image.py -> mesh3d.py) and seeded here by
ingest/seed_demo_products.py — to retailer storefronts, gated by a
per-retailer API key. This is the piece a retailer's own backend calls; a
shopper's browser never talks to it directly (see retailer_site/api_client.py).

Run:  .venv/bin/python catalog_api/server.py     (http://localhost:8100)
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

import storage

# One hardcoded demo key stands in for a real per-retailer key lookup.
DEMO_API_KEY = os.environ.get("CATALOG_API_KEY", "demo-retailer-key-123")

app = FastAPI(title="Image3D Retailer Catalog API")


def _require_key(x_api_key: str | None) -> None:
    if x_api_key != DEMO_API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/products")
async def list_products(x_api_key: str | None = Header(default=None)):
    _require_key(x_api_key)
    return {"products": storage.list_products()}


@app.get("/api/products/{product_id}")
async def get_product(product_id: str, x_api_key: str | None = Header(default=None)):
    _require_key(x_api_key)
    product = storage.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@app.get("/api/products/{product_id}/model.glb")
async def get_model(product_id: str, x_api_key: str | None = Header(default=None)):
    _require_key(x_api_key)
    if storage.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail="product not found")
    path = storage.model_path(product_id)
    if path is None:
        raise HTTPException(status_code=404, detail="no 3D model for this product")
    return FileResponse(path, media_type="model/gltf-binary", filename=path.name)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8100)))
