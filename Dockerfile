FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-cad.txt backend/requirements-cad.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-cad.txt \
    && python -c "import cadquery; from OCP.GeomAbs import GeomAbs_Cylinder; print('cadquery ok')"

COPY backend/app ./backend/app
COPY database ./database

ENV PYTHONPATH=/app/backend
ENV PKB_ROOT=/app
ENV PKB_DB_PATH=/app/data/pkb.db
ENV PKB_TARGET_TOTAL=50000

WORKDIR /app/backend

EXPOSE 8090

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8090}"]
