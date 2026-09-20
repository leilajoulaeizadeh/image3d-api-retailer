"""Demo retailer storefront: a thin Streamlit client of the catalog API
(catalog_api/server.py). Stands in for a real retailer's website — shoppers
browse the catalog and click "View in 3D" on a product to load and play with
its 3D model, exactly like an embedded widget on a real product page would.

Run:  streamlit run retailer_site/app.py
API:  set CATALOG_API_URL / CATALOG_API_KEY in .streamlit/secrets.toml (or
      env vars) — see .streamlit/secrets.toml.example
"""

from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Acme Home — Demo Store", page_icon="🛋️", layout="wide")

st.title("🛋️ Acme Home")

if "selected_product" not in st.session_state:
    st.session_state.selected_product = None

try:
    products = api.list_products()
except api.ApiError as e:
    st.error(f"Could not load the catalog: {e}")
    st.stop()


@st.cache_data(ttl=300, show_spinner=False)
def _photo(product_id: str) -> str | None:
    try:
        return api.get_photo_data_url(product_id)
    except api.ApiError:
        return None


def _show_photo(data_url: str, height: int) -> None:
    """A photo boxed to a fixed height regardless of its original aspect
    ratio, so photos of different shapes still line up (card grid, and next
    to the 3D viewer in the detail view) -- 'contain', not 'cover', so the
    whole photo stays visible (letterboxed) instead of being cropped, which
    'cover' would do more or less aggressively depending on viewport width."""
    st.markdown(
        f"""
        <div style="width:100%;height:{height}px;border-radius:8px;
             border:1px solid #e6e6e6;background:#fafafa;
             display:flex;align-items:center;justify-content:center;overflow:hidden;">
          <img src="{data_url}" style="max-width:100%;max-height:100%;object-fit:contain;">
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_viewer(mesh_url: str, height: int = 480) -> None:
    st.components.v1.html(
        f"""
        <script type="module"
          src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
        <model-viewer src="{mesh_url}" camera-controls auto-rotate
          shadow-intensity="1" exposure="1"
          style="width:100%;height:{height}px;background:#ffffff;border-radius:8px;
                 border:1px solid #e6e6e6;">
        </model-viewer>
        """,
        height=height + 16,
    )


selected = st.session_state.selected_product

if selected is None:
    st.caption(
        "Demo retailer storefront — product 3D models are served on demand from "
        "the Image3D catalog API, the same way a real retailer's site would."
    )

if selected is not None:
    product = next((p for p in products if p["id"] == selected), None)
    if product is None:
        st.session_state.selected_product = None
        st.rerun()

    if st.button("← Back to catalog"):
        st.session_state.selected_product = None
        st.rerun()

    st.subheader(f"{product['name']} — ${product['price']:.2f}")
    if product["description"]:
        st.caption(product["description"])

    DETAIL_HEIGHT = 480

    photo_col, model_col = st.columns(2)
    with photo_col:
        if product.get("has_photo"):
            photo = _photo(product["id"])
            if photo:
                _show_photo(photo, DETAIL_HEIGHT)
                st.caption("Original photo")
    with model_col:
        with st.spinner("Loading 3D model…"):
            try:
                mesh_url = api.get_model_data_url(product["id"])
            except api.ApiError as e:
                st.error(f"Could not load this product's 3D model: {e}")
                st.stop()
        _show_viewer(mesh_url, DETAIL_HEIGHT)
        st.caption("Drag to rotate, scroll to zoom — same viewer a retailer would embed on a product page.")

else:
    CARD_PHOTO_HEIGHT = 200

    categories = sorted({p["category"] for p in products})
    tabs = st.tabs(["All"] + categories)
    for tab, cat in zip(tabs, ["All"] + categories):
        with tab:
            shown = products if cat == "All" else [p for p in products if p["category"] == cat]
            cols = st.columns(3)
            for i, product in enumerate(shown):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{product['name']}**")
                        st.caption(product["category"])
                        photo = _photo(product["id"]) if product.get("has_photo") else None
                        if photo:
                            _show_photo(photo, CARD_PHOTO_HEIGHT)
                        else:
                            st.write(product["description"])
                        st.markdown(f"**${product['price']:.2f}**")
                        if st.button("🧊 View in 3D", key=f"view-{cat}-{product['id']}"):
                            st.session_state.selected_product = product["id"]
                            st.rerun()
