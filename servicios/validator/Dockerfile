FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY validator.py .

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# -u: salida sin buffer (logs en tiempo real con docker logs)
CMD ["python", "-u", "validator.py"]
