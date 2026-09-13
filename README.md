# Image3D — Retailer API demo

Shows the "core product → API → retailer website" flow end to end:

1. **Core product** — the image → 3D pipeline (a separate project,
   [`image_reconstruction`](../image_reconstruction)): retailer photos in,
   GLB meshes out.
2. **Local storage** (`storage/`) — a small library of those GLBs plus a
   `products.json` catalog. `ingest/seed_demo_products.py` fills it; for this
   demo it seeds a handful of free sample meshes instead of running the real
   pipeline, so it works with no photos and no `FAL_KEY`.
3. **Catalog API** (`catalog_api/`, FastAPI) — what a retailer's backend
   calls to list products and fetch a model, gated by an API key
   (`X-API-Key` header).
4. **Retailer site** (`retailer_site/`, Streamlit) — a demo storefront:
   product grid, "View in 3D" per product, drag-to-rotate / scroll-to-zoom
   viewer. Stands in for the widget a real retailer would embed on a product
   page.

```
storage (GLBs + products.json)
    ↑ read by
catalog_api/server.py  --X-API-Key-->  retailer_site/app.py  -->  shopper's browser
   (:8100)                                  (:8501)
```

The retailer site holds the API key server-side and never sends it to the
browser — it fetches each GLB itself and re-embeds it as a data URL for
`<model-viewer>`, so a shopper's browser never needs to know the key.

## Run locally

```bash
python -m venv .venv && .venv/bin/pip install -r catalog_api/requirements.txt
.venv/bin/python ingest/seed_demo_products.py   # one-time: downloads sample GLBs
.venv/bin/python catalog_api/server.py          # http://localhost:8100
```

In a second terminal:

```bash
cd retailer_site
pip install -r requirements.txt
streamlit run app.py                            # http://localhost:8501
```

Point the retailer site at a different catalog API / key with
`CATALOG_API_URL` / `CATALOG_API_KEY` (env vars, or
`retailer_site/.streamlit/secrets.toml` — copy `secrets.toml.example`).

## Going from demo to real

`ingest/build_from_photos.py` replaces `seed_demo_products.py`: for each
product in a manifest (`ingest/products_input.example.json` shows the shape),
it calls the `image_reconstruction` backend over HTTP —
`POST /api/detect` to crop the product out of its photo, `POST
/api/generate-view` for a clean angled studio shot, `POST /api/generate-mesh`
for the GLB — and writes the result into `storage/` exactly like the demo
script does. Nothing in `catalog_api/` or `retailer_site/` needs to change —
they only know about `storage/`.

```bash
cd ../image_reconstruction && pip install -r requirements.txt
.venv/bin/python server.py                      # http://localhost:8000, needs FAL_KEY in .env

cd ../image3d_api_retailer
pip install -r ingest/requirements.txt
python ingest/build_from_photos.py ingest/products_input.example.json
```

Each product costs a small, real fal.ai charge (view generation + mesh
reconstruction — see `image_reconstruction/SERVICES_AND_COSTS.md`); a product
whose GLB already exists in `storage/models/` is skipped on rerun. The
backend only needs to be running during ingestion, not while serving the
catalog.

## Deploy

Two independent deploys — `retailer_site` is only ever a client of
`catalog_api`, so `catalog_api` has to be reachable on the internet first.

**`catalog_api` → Render**, via the root `Dockerfile` + `render.yaml` (same
pattern as `image_reconstruction`'s own deploy config). It bakes in whatever
is currently committed under `storage/`, so re-deploy after any ingest run
whose results should go live:

1. On [render.com](https://render.com): **New → Blueprint**, point it at this
   repo. Render reads `render.yaml` and provisions the `image3d-catalog-api`
   web service from the `Dockerfile` automatically.
2. Set `CATALOG_API_KEY` in that service's **Environment** tab to a real
   secret (it defaults to the demo key otherwise).
3. Note the service's `https://….onrender.com` URL once it's live.

**`retailer_site` → Streamlit Community Cloud**:

1. On [share.streamlit.io](https://share.streamlit.io): **New app**, pick
   this repo/branch, set the main file path to `retailer_site/app.py`.
2. In that app's **Settings → Secrets**, set:
   ```toml
   CATALOG_API_URL = "https://<your-render-service>.onrender.com"
   CATALOG_API_KEY = "<the same value set on Render>"
   ```
3. If it prompts visitors to log in, the app's sharing setting is set to
   restricted — switch **Who can view this app** to public.
