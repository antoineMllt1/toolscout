# ── Build React frontend ──────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend-react
COPY frontend-react/package*.json ./
RUN npm install
COPY frontend-react/ ./
RUN npm run build   # outputs to /app/frontend/


# ── Python backend ────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libgdk-pixbuf2.0-0 \
    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 \
    libpangocairo-1.0-0 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxkbcommon0 \
    libxrandr2 libxrender1 libxss1 libxtst6 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (--with-deps handles remaining OS libs)
RUN playwright install chromium --with-deps

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend from first stage
COPY --from=frontend-builder /app/frontend/ ./frontend/

# Persistent data dir for SQLite
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/data.db

WORKDIR /app/backend

EXPOSE 8000

# Railway injects $PORT dynamically; fallback to 8000 for local Docker
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
