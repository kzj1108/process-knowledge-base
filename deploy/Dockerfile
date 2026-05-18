FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY database ./database

ENV PKB_ROOT=/app
ENV PKB_DB_PATH=/data/process_kb.db
ENV PYTHONPATH=/app
ENV PKB_API_KEY=change-me-in-production
ENV PKB_ADMIN_USER=admin
ENV PKB_ADMIN_PASS=change-me-in-production

EXPOSE 8090

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
