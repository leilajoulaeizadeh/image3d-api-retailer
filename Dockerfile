# catalog_api — serves the shared R2-backed catalog over a small
# API-key-gated FastAPI app. Needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
# R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME set at runtime (see render.yaml).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8100

WORKDIR /app

COPY catalog_api/requirements.txt ./catalog_api/requirements.txt
RUN pip install -r catalog_api/requirements.txt

COPY catalog_api/ ./catalog_api/

WORKDIR /app/catalog_api
EXPOSE 8100
# server.py binds 0.0.0.0:$PORT by default.
CMD ["python", "server.py"]
