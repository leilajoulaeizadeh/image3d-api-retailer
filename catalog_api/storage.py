"""Shared storage for the product catalog: a products.json object plus GLB
mesh objects in a Cloudflare R2 bucket (S3-compatible). ingest/build_from_photos.py
writes to this same bucket, so a new reconstruction is live here as soon as
it's uploaded -- no redeploy needed. Swapping the backing store again later
means changing only this module.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

PRODUCTS_KEY = "products.json"
MODELS_PREFIX = "models/"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set -- catalog_api needs R2 credentials to start")
    return value


_BUCKET = _required("R2_BUCKET_NAME")
_client = boto3.client(
    "s3",
    endpoint_url=f"https://{_required('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=_required("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=_required("R2_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def _load() -> list[dict[str, Any]]:
    try:
        obj = _client.get_object(Bucket=_BUCKET, Key=PRODUCTS_KEY)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return []
        raise
    return json.loads(obj["Body"].read())


def list_products() -> list[dict[str, Any]]:
    """Metadata only, no model_file path (that's an internal storage detail)."""
    return [{k: v for k, v in p.items() if k != "model_file"} for p in _load()]


def get_product(product_id: str) -> dict[str, Any] | None:
    for p in _load():
        if p["id"] == product_id:
            return {k: v for k, v in p.items() if k != "model_file"}
    return None


def model_bytes(product_id: str) -> bytes | None:
    for p in _load():
        if p["id"] == product_id:
            try:
                obj = _client.get_object(Bucket=_BUCKET, Key=MODELS_PREFIX + p["model_file"])
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    return None
                raise
            return obj["Body"].read()
    return None
