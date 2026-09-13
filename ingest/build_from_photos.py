"""Fills the shared product catalog (a Cloudflare R2 bucket) from real
retailer photos via the image_reconstruction pipeline's HTTP API -- the
production replacement for seed_demo_products.py.

For each product listed in a manifest: finds and crops the product out of its
photo (POST /api/detect -- photos may show clutter or more than one object),
generates a clean angled studio view of the crop (POST /api/generate-view),
reconstructs a GLB from that view (POST /api/generate-mesh), and uploads the
result into the same R2 bucket catalog_api reads from -- catalog_api/storage.py
has the exact key layout (products.json + models/<id>.glb). A product is live
on the deployed catalog_api as soon as this script finishes; no redeploy needed.

Needs the image_reconstruction backend running with FAL_KEY set there (see
../../image_reconstruction/README.md) -- this script only talks to it over
HTTP, the same way retailer_site talks to catalog_api. Also needs R2
credentials in the environment: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME (the same ones catalog_api uses).

Each fal.ai call costs real money (SERVICES_AND_COSTS.md in that project); a
product whose GLB already exists in the bucket is skipped on rerun.

Run:  python ingest/build_from_photos.py ingest/products_input.json
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image

BACKEND_URL = "http://localhost:8000"  # image_reconstruction/server.py
IMAGE_MODEL = "fal-ai/nano-banana/edit"  # cheap default view-generation model
MESH_MODEL = "fal-ai/trellis"  # cheap default image-to-3D model
CROP_MARGIN = 0.08  # fraction of box size added on each side before generate-view

PRODUCTS_KEY = "products.json"
MODELS_PREFIX = "models/"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set -- this script needs the same R2 credentials as catalog_api")
    return value


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{_required('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=_required("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_required("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _load_catalog(r2, bucket: str) -> list[dict[str, Any]]:
    try:
        obj = r2.get_object(Bucket=bucket, Key=PRODUCTS_KEY)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return []
        raise
    return json.loads(obj["Body"].read())


def _save_catalog(r2, bucket: str, catalog: list[dict[str, Any]]) -> None:
    r2.put_object(
        Bucket=bucket, Key=PRODUCTS_KEY,
        Body=json.dumps(catalog, indent=2).encode(), ContentType="application/json",
    )


def _model_exists(r2, bucket: str, model_file: str) -> bool:
    try:
        r2.head_object(Bucket=bucket, Key=MODELS_PREFIX + model_file)
        return True
    except ClientError:
        return False


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _decode_data_url(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[1])


def _pick_instance(instances: list[dict[str, Any]], label_hint: str | None) -> dict[str, Any] | None:
    """The detected object to reconstruct, or None if nothing was detected.
    With a label_hint, prefer whichever matching instance the detector is most
    confident about; otherwise just the most confident instance in the photo."""
    if not instances:
        return None
    if label_hint:
        matches = [i for i in instances if label_hint.lower() in i["label"].lower()]
        if matches:
            return max(matches, key=lambda i: i["score"])
        print(f"    no detection matched label_hint {label_hint!r}; using the most confident instance instead")
    return max(instances, key=lambda i: i["score"])


def _crop_to_data_url(photo: Path, box: list[float], margin: float) -> str:
    img = Image.open(photo).convert("RGB")
    w, h = img.size
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    x0 = max(0, x0 - bw * margin)
    y0 = max(0, y0 - bh * margin)
    x1 = min(w, x1 + bw * margin)
    y1 = min(h, y1 + bh * margin)
    crop = img.crop((x0, y0, x1, y1))
    buf = BytesIO()
    crop.save(buf, format="JPEG", quality=92)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def build_product(entry: dict[str, Any], photo: Path, backend: str, r2, bucket: str) -> dict[str, Any]:
    print(f"  {entry['id']}: detecting object in {photo.name}...")
    detect = requests.post(f"{backend}/api/detect", json={"image": _data_url(photo)}, timeout=60)
    detect.raise_for_status()
    instance = _pick_instance(detect.json()["instances"], entry.get("label_hint"))
    if instance is not None:
        print(f"    found {instance['label']!r} ({instance['score']:.2f} confidence)")
        crop_url = _crop_to_data_url(photo, instance["box"], CROP_MARGIN)
    else:
        print("    no confident detection -- using the full photo as the crop")
        crop_url = _data_url(photo)

    print(f"  {entry['id']}: generating studio view...")
    view = requests.post(
        f"{backend}/api/generate-view",
        json={"model": IMAGE_MODEL, "image": crop_url, "label": entry["name"], "view": "angled"},
        timeout=180,
    )
    view.raise_for_status()
    view_data = view.json()

    print(f"  {entry['id']}: reconstructing mesh...")
    mesh = requests.post(
        f"{backend}/api/generate-mesh",
        json={"images": [view_data["url"]], "label": entry["name"], "model": MESH_MODEL},
        timeout=180,
    )
    mesh.raise_for_status()
    mesh_data = mesh.json()

    model_file = f"{entry['id']}.glb"
    r2.put_object(
        Bucket=bucket, Key=MODELS_PREFIX + model_file,
        Body=_decode_data_url(mesh_data["mesh"]), ContentType="model/gltf-binary",
    )
    cost = (view_data.get("cost") or 0) + (mesh_data.get("cost") or 0)
    print(f"    uploaded {model_file} ({mesh_data['vertices']} verts) -- ~${cost:.3f}")

    return {
        "id": entry["id"],
        "name": entry["name"],
        "category": entry["category"],
        "price": entry["price"],
        "description": entry["description"],
        "model_file": model_file,
    }


def _metadata_only(entry: dict[str, Any], model_file: str) -> dict[str, Any]:
    return {
        "id": entry["id"], "name": entry["name"], "category": entry["category"],
        "price": entry["price"], "description": entry["description"], "model_file": model_file,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON file listing products to build")
    parser.add_argument("--backend", default=BACKEND_URL, help="image_reconstruction server URL")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    r2 = _r2_client()
    bucket = _required("R2_BUCKET_NAME")
    backend = args.backend.rstrip("/")
    catalog = {p["id"]: p for p in _load_catalog(r2, bucket)}

    for entry in manifest:
        model_file = f"{entry['id']}.glb"
        if _model_exists(r2, bucket, model_file):
            print(f"  {entry['id']}: {model_file} already in R2, skipping reconstruction")
            catalog[entry["id"]] = _metadata_only(entry, model_file)
            continue
        photo = args.manifest.parent / entry["photo"]
        catalog[entry["id"]] = build_product(entry, photo, backend, r2, bucket)

    _save_catalog(r2, bucket, list(catalog.values()))
    print(f"Wrote {len(catalog)} products to R2 bucket {bucket!r}")


if __name__ == "__main__":
    main()
