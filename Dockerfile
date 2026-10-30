FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=frontend /frontend/dist ./frontend/dist
COPY examples ./examples
ENV PYTHONUNBUFFERED=1 KANCA_DB_PATH=/data/kanca.db
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
