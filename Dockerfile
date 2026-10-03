# syntax=docker/dockerfile:1
# Dos imágenes desde el mismo archivo: --target backend y --target frontend.
FROM python:3.12-slim-bookworm AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --chown=app:app backend/app ./app
USER app
EXPOSE 8000
# El backend solo es accesible dentro de la red de Compose, detrás de Caddy.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--no-access-log"]

FROM node:24-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM caddy:2-alpine AS frontend

COPY deployment/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/dist /srv

RUN caddy validate \
    --config /etc/caddy/Caddyfile \
    --adapter caddyfile

EXPOSE 8080
