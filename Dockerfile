# ── Build React frontend ──────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend-react
COPY frontend-react/package*.json ./
RUN npm install
COPY frontend-react/ ./
RUN npm run build   # outputs to /app/frontend/


# ── Python backend ────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and the matching OS packages for the current Debian base image.
RUN python -m playwright install --with-deps chromium

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend from first stage
COPY --from=frontend-builder /app/frontend/ ./frontend/

# Persistent data dir for SQLite
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/data.db

WORKDIR /app/backend

EXPOSE 8080

# Railway injects $PORT dynamically; fallback to 8080 for local Docker
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-config logging.json
