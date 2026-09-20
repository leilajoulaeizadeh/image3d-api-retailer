"""Thin HTTP client the retailer demo site uses to talk to the catalog API.

The API key lives here, server-side in the Streamlit process — it never
reaches the shopper's browser. GLB bytes fetched with it are re-embedded as a
data URL for <model-viewer> rather than linked to directly, so the browser
never has to send the key itself.
"""

from __future__ import annotations

import base64
import os
from typing import Any

import requests
import streamlit as st


class ApiError(RuntimeError):
    """Something went wrong talking to the catalog API."""


def _base_url() -> str:
    try:
        url = st.secrets.get("CATALOG_API_URL")
    except Exception:
        url = None
    url = url or os.environ.get("CATALOG_API_URL") or "http://localhost:8100"
    return url.rstrip("/")


def _api_key() -> str:
    try:
        key = st.secrets.get("CATALOG_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("CATALOG_API_KEY") or "demo-retailer-key-123"


def _headers() -> dict[str, str]:
    return {"X-API-Key": _api_key()}


def _detail(r: requests.Response) -> str:
    try:
        return r.json().get("detail", r.text)
    except Exception:  # noqa: BLE001
        return r.text or f"HTTP {r.status_code}"


def list_products() -> list[dict[str, Any]]:
    try:
        r = requests.get(f"{_base_url()}/api/products", headers=_headers(), timeout=10)
    except requests.RequestException as e:
        raise ApiError(f"could not reach the catalog API: {e}") from e
    if not r.ok:
        raise ApiError(_detail(r))
    return r.json()["products"]


def get_photo_data_url(product_id: str) -> str | None:
    """The product's original photo as a data URL, or None if it has none."""
    try:
        r = requests.get(
            f"{_base_url()}/api/products/{product_id}/photo",
            headers=_headers(), timeout=15,
        )
    except requests.RequestException as e:
        raise ApiError(f"could not reach the catalog API: {e}") from e
    if r.status_code == 404:
        return None
    if not r.ok:
        raise ApiError(_detail(r))
    mime = r.headers.get("Content-Type", "image/jpeg")
    b64 = base64.b64encode(r.content).decode()
    return f"data:{mime};base64,{b64}"


def get_model_data_url(product_id: str) -> str:
    try:
        r = requests.get(
            f"{_base_url()}/api/products/{product_id}/model.glb",
            headers=_headers(), timeout=30,
        )
    except requests.RequestException as e:
        raise ApiError(f"could not reach the catalog API: {e}") from e
    if not r.ok:
        raise ApiError(_detail(r))
    b64 = base64.b64encode(r.content).decode()
    return f"data:model/gltf-binary;base64,{b64}"
