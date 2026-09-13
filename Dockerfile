# catalog_api — serves storage/ over a small API-key-gated FastAPI app.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8100

WORKDIR /app

COPY catalog_api/requirements.txt ./catalog_api/requirements.txt
RUN pip install -r catalog_api/requirements.txt

COPY catalog_api/ ./catalog_api/
COPY storage/ ./storage/

WORKDIR /app/catalog_api
EXPOSE 8100
# server.py binds 0.0.0.0:$PORT by default.
CMD ["python", "server.py"]
