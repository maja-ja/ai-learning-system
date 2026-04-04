### Multi-stage: build frontend → slim Python runtime
### Works on amd64 and arm64 (RPi 5)

FROM node:20-slim AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --ignore-scripts
COPY web/ .
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libwebp7 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY start.py serve_portable.py ./
COPY --from=frontend /web/dist /app/web/dist

ENV SERVE_WEB_DIST=1
ENV SKIP_WEB_BUILD=1
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
