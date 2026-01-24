FROM python:3.9-slim

WORKDIR /app

# Deshabilitar buffer para ver logs en tiempo real
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Por defecto ejecuta el main
CMD ["python", "main.py"]