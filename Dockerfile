# Stage 1: Build React + TypeScript + Tailwind frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python 3.13 + FastAPI + SQLite + ONNX Vision AI + built React SPA
FROM python:3.13-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOOMOS_FRONTEND_DIST=/app/frontend/dist \
    PORT=8000

# Minimal system libraries required by opencv-python-headless & Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure default persistent data directories exist
RUN mkdir -p /app/backend/data/uploads /app/backend/data/backups

EXPOSE 8000
CMD ["python", "backend/scripts/cloud_start.py"]
