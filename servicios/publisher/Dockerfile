FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY publisher.py .

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Argumentos por defecto: modo normal.
ENTRYPOINT ["python", "publisher.py"]
CMD ["--mode", "normal", "--rate", "1.0"]
