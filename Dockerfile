# Single-container build: React UI compiled and served by FastAPI. Built remotely by Cloud Build
# (`gcloud run deploy --source .`), so no local Docker is required.
FROM node:24-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=ui /ui/dist /app/frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist CORS_ORIGINS='[]'
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
