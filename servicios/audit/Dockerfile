FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY audit.py .

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-u", "audit.py"]