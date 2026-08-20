# Production image: React UI + FastAPI API in one service (SQLite demo)
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

ENV PYTHONPATH=/app
ENV DEMO_MODE=true
ENV AI_PROVIDER=mock
ENV DATA_PROVIDER=mock
ENV DATABASE_URL=sqlite:////tmp/finance_control_tower.db
ENV CORS_ORIGINS=*
ENV SERVE_FRONTEND=true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
