FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar sqlite3 para acceso externo
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

COPY metrics_storage.py .

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-u", "metrics_storage.py"]