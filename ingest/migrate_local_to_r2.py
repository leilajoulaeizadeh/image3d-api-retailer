"""One-off: uploads the current local storage/ (products.json + models/*.glb)
into the R2 bucket now used as the shared catalog store, so switching
catalog_api over to R2 doesn't lose (or require re-paying fal.ai for) the
products already built. Not needed after this migration.

Needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
in the environment -- the same ones catalog_api uses.

Run:  python ingest/migrate_local_to_r2.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
from botocore.client import Config

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set -- this script needs the same R2 credentials as catalog_api")
    return value


def main() -> None:
    r2 = boto3.client(
        "s3",
        endpoint_url=f"https://{_required('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=_required("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_required("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket = _required("R2_BUCKET_NAME")

    products = json.loads((STORAGE_DIR / "products.json").read_text())
    for p in products:
        glb = STORAGE_DIR / "models" / p["model_file"]
        r2.put_object(
            Bucket=bucket, Key=f"models/{p['model_file']}",
            Body=glb.read_bytes(), ContentType="model/gltf-binary",
        )
        print(f"  uploaded models/{p['model_file']}")

    r2.put_object(
        Bucket=bucket, Key="products.json",
        Body=json.dumps(products, indent=2).encode(), ContentType="application/json",
    )
    print(f"Wrote products.json ({len(products)} products) to bucket {bucket!r}")


if __name__ == "__main__":
    main()
