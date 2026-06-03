# syntax=docker/dockerfile:1
#
# Mind Video — single-container image for Google Cloud Run.
#
#   Stage 1 (frontend) : compile the Vite/React app to static files.
#   Stage 2 (runtime)  : FastAPI + ffmpeg; serves the API AND the built bundle
#                        on one port, so the UI and API share one origin.
#
# Build:   docker build -t mind-video .
# Run:     docker run -p 8080:8080 --env-file .env mind-video

# ---------------------------------------------------------------------------
# Stage 1 — build the React frontend
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend

WORKDIR /build

# Install deps first for layer caching.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build. VITE_API_BASE is intentionally left unset → API_BASE === "" →
# the bundle calls the same origin that serves it (the FastAPI server).
COPY frontend/ ./
RUN rm -f .env .env.* && npm run build

# ---------------------------------------------------------------------------
# Stage 2 — Python runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    FRONTEND_DIST=/app/frontend/dist

# ffmpeg is required by the render pipeline (TTS atempo + concat).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first for layer caching.
COPY server/requirements.txt ./server/requirements.txt
RUN pip install -r server/requirements.txt

# App code + built frontend.
COPY server/ ./server/
COPY --from=frontend /build/dist ./frontend/dist

# Drop privileges.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Cloud Run injects PORT; default to 8080 for plain `docker run`.
CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]
