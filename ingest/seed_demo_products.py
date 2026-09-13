"""Seeds local storage with a handful of retailer products and their 3D models.

In production this step is: retailer photos -> the core image_reconstruction
pipeline (detectors.py to crop, fal_image.py for a canonical studio view,
mesh3d.py to reconstruct a GLB) -> this storage. This demo skips straight to
the GLB, using a few free CC0/Apache-licensed sample meshes from the Khronos
glTF-Sample-Assets repo, so the catalog API + retailer site can be exercised
without product photos or a FAL_KEY. To go from "demo" to "real", replace the
_download() step below with a call into that pipeline and point model_file at
its output.

Run:  python ingest/seed_demo_products.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
MODELS_DIR = STORAGE_DIR / "models"
PRODUCTS_FILE = STORAGE_DIR / "products.json"

ASSET_BASE = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models"

# `asset` is the glTF-Sample-Assets model name (removed before writing
# products.json — it's a seeding detail, not catalog metadata).
PRODUCTS = [
    {
        "id": "lounge-chair",
        "name": "Sheen Lounge Chair",
        "category": "Furniture",
        "price": 249.00,
        "description": "Upholstered lounge chair with a soft sheen fabric finish.",
        "asset": "SheenChair",
        "model_file": "lounge-chair.glb",
    },
    {
        "id": "velvet-sofa",
        "name": "Glam Velvet Sofa",
        "category": "Furniture",
        "price": 899.00,
        "description": "Two-seat sofa in deep-pile velvet.",
        "asset": "GlamVelvetSofa",
        "model_file": "velvet-sofa.glb",
    },
    {
        "id": "running-shoe",
        "name": "Trail Running Shoe",
        "category": "Footwear",
        "price": 119.99,
        "description": "Lightweight trail running shoe, shown in one of its colorways.",
        "asset": "MaterialsVariantsShoe",
        "model_file": "running-shoe.glb",
    },
]


def _download(asset: str, dest: Path) -> None:
    url = f"{ASSET_BASE}/{asset}/glTF-Binary/{asset}.glb"
    print(f"  downloading {asset} -> {dest.name}")
    urllib.request.urlretrieve(url, dest)


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = []
    for product in PRODUCTS:
        dest = MODELS_DIR / product["model_file"]
        if dest.exists():
            print(f"  {dest.name} already present, skipping download")
        else:
            _download(product["asset"], dest)
        catalog.append({k: v for k, v in product.items() if k != "asset"})
    PRODUCTS_FILE.write_text(json.dumps(catalog, indent=2))
    print(f"Wrote {len(catalog)} products to {PRODUCTS_FILE}")


if __name__ == "__main__":
    main()
