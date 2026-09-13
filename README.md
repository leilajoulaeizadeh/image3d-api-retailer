# Image3D — Retailer API demo

https://claude.ai/code/artifact/622f3807-c262-413b-a7a3-ec22af65c719

Shows the "core product → API → retailer website" flow end to end:

1. **Core product** — the image → 3D pipeline (a separate project,
   [`image_reconstruction`](../image_reconstruction)): retailer photos in,
   GLB meshes out.
2. **Shared storage** (a Cloudflare R2 bucket) — `products.json` plus the GLB
   meshes, read and written through `catalog_api/storage.py`.
   `ingest/build_from_photos.py` fills it from real photos;
   `ingest/seed_demo_products.py` is the old local-only demo path (five free
   sample meshes, no photos or `FAL_KEY` needed) and no longer feeds the
   deployed catalog. A product uploaded to the bucket is live immediately —
   no redeploy of `catalog_api` needed.
3. **Catalog API** (`catalog_api/`, FastAPI) — what a retailer's backend
   calls to list products and fetch a model, gated by an API key
   (`X-API-Key` header).
4. **Retailer site** (`retailer_site/`, Streamlit) — a demo storefront:
   product grid, "View in 3D" per product, drag-to-rotate / scroll-to-zoom
   viewer. Stands in for the widget a real retailer would embed on a product
   page.

```
R2 bucket (GLBs + products.json)
    ↑ read/written by
ingest/build_from_photos.py ──┘
    ↑ read by
catalog_api/server.py  --X-API-Key-->  retailer_site/app.py  -->  shopper's browser
   (:8100)                                  (:8501)
```

The retailer site holds the API key server-side and never sends it to the
browser — it fetches each GLB itself and re-embeds it as a data URL for
`<model-viewer>`, so a shopper's browser never needs to know the key.

## Run locally

Needs a Cloudflare R2 bucket first (see **Deploy** below for how to create
one) — export its credentials, then:

```bash
export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET_NAME=...

python -m venv .venv && .venv/bin/pip install -r catalog_api/requirements.txt
.venv/bin/python catalog_api/server.py          # http://localhost:8100
```

catalog_api reads/writes that bucket directly — there's nothing to seed
locally first. To put something in it, either run `ingest/build_from_photos.py`
(below) or `ingest/migrate_local_to_r2.py` if you still have an old local
`storage/` to carry over.

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
for the GLB — and uploads the result straight into the R2 bucket, using the
same `R2_*` credentials as `catalog_api`. A product is visible on the
deployed catalog as soon as the script finishes; nothing to redeploy, and
nothing in `catalog_api/` or `retailer_site/` needs to change either way.

```bash
cd ../image_reconstruction && pip install -r requirements.txt
.venv/bin/python server.py                      # http://localhost:8000, needs FAL_KEY in .env

cd ../image3d_api_retailer
pip install -r ingest/requirements.txt
export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET_NAME=...
python ingest/build_from_photos.py ingest/products_input.example.json
```

Each product costs a small, real fal.ai charge (view generation + mesh
reconstruction — see `image_reconstruction/SERVICES_AND_COSTS.md`); a product
whose GLB already exists in the bucket is skipped on rerun. The backend only
needs to be running during ingestion, not while serving the catalog.

## Deploy

Three things, in order: an R2 bucket, `catalog_api` (Render), then
`retailer_site` (Streamlit Community Cloud). `catalog_api` is the only
service that has to be reachable on the internet before `retailer_site` will
show anything.

**R2 bucket** (Cloudflare, shared by `catalog_api` and `ingest/build_from_photos.py`):

1. Cloudflare dashboard → **R2** → **Create bucket** (e.g. `image3d-catalog`).
2. **R2 → Manage API tokens → Create API token**, scoped to that bucket with
   Object Read & Write. This gives an Access Key ID + Secret Access Key.
3. Note your Cloudflare **Account ID** (shown on the R2 overview page) and
   the bucket name — together with the token, that's all four `R2_*` values
   used everywhere below.
4. If you have an existing local `storage/` to carry over (rather than
   starting empty), run `ingest/migrate_local_to_r2.py` once with those
   credentials exported.

**`catalog_api` → Render**, via the root `Dockerfile` + `render.yaml` (same
pattern as `image_reconstruction`'s own deploy config):

1. On [render.com](https://render.com): **New → Blueprint**, point it at this
   repo. Render reads `render.yaml` and provisions the `image3d-catalog-api`
   web service from the `Dockerfile` automatically.
2. In that service's **Environment** tab, set `CATALOG_API_KEY` (a real
   secret — it defaults to the demo key otherwise) and the four `R2_*`
   variables from above.
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
