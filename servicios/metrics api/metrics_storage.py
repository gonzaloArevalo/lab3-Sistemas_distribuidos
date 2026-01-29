"""
Metrics Storage Service - Lab 3 País X.
Consume métricas agregadas y las almacena en SQLite para consulta directa.
Implementación simplificada sin API HTTP.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

import pika

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Configuración
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
EXCHANGE = "events_topic"
METRICS_TOPIC = "metrics.daily"
QUEUE_METRICS_STORAGE = "metrics_storage_queue"
DB_PATH = os.getenv("DB_PATH", "/app/metrics_data/metrics.db")

# Lock para thread-safe database access
db_lock = threading.Lock()


def log_json(level: str, msg: str, **kwargs: Any) -> None:
    """Genera logs estructurados en formato JSON"""
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "level": level,
        "service": "metrics_storage",
        "message": msg,
        **kwargs,
    }
    logger.info(json.dumps(entry))


def init_database() -> None:
    """Inicializa la base de datos SQLite con el esquema requerido"""
    conn = sqlite3.connect(DB_PATH)
    
    # Tabla de métricas diarias
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            region TEXT NOT NULL,
            metrics TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(date, region)
        )
    """)
    
    # Índices para mejor rendimiento
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_date_region ON daily_metrics (date, region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics (date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_region ON daily_metrics (region)")
    
    conn.commit()
    conn.close()
    log_json("INFO", "Base de datos inicializada", db_path=DB_PATH)


def store_metric(metric: Dict[str, Any]) -> None:
    """Almacena una métrica en la base de datos (thread-safe)"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_metrics 
                (date, region, metrics, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    metric.get("date"),
                    metric.get("region"),
                    json.dumps(metric.get("metrics", {})),
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                )
            )
            conn.commit()
            conn.close()
        
        log_json("DEBUG", "Métrica almacenada", 
                date=metric.get("date"), 
                region=metric.get("region"))
    except sqlite3.Error as e:
        log_json("ERROR", "Error almacenando métrica", 
                error=str(e), 
                date=metric.get("date"), 
                region=metric.get("region"))


def start_consumer() -> None:
    """Inicia el consumidor de RabbitMQ"""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                connection_attempts=3,
                retry_delay=2,
            )
            rabbit_conn = pika.BlockingConnection(params)
            ch = rabbit_conn.channel()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                log_json("WARNING", "Error conectando a RabbitMQ, reintentando", 
                        error=str(e), attempt=attempt + 1, max_retries=max_retries)
                time.sleep(retry_delay)
            else:
                log_json("ERROR", "No se pudo conectar a RabbitMQ", error=str(e))
                return

    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(QUEUE_METRICS_STORAGE, durable=True)
    ch.queue_bind(queue=QUEUE_METRICS_STORAGE, exchange=EXCHANGE, routing_key=METRICS_TOPIC)
    ch.basic_qos(prefetch_count=1)

    metrics_received = 0

    def on_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, 
                  properties: pika.BasicProperties, body: bytes) -> None:
        nonlocal metrics_received
        try:
            metric = json.loads(body)
            store_metric(metric)
            metrics_received += 1
            
            if metrics_received % 10 == 0:
                log_json("INFO", "Métricas procesadas", count=metrics_received)
            
        except json.JSONDecodeError as e:
            log_json("ERROR", "JSON inválido en métrica", error=str(e))
        except Exception as e:
            log_json("ERROR", "Error procesando métrica", error=str(e))
        
        channel.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=QUEUE_METRICS_STORAGE, on_message_callback=on_message)
    log_json("INFO", "Consumidor de métricas iniciado", queue=QUEUE_METRICS_STORAGE, topic=METRICS_TOPIC)

    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        log_json("INFO", "Consumidor detenido", metrics_processed=metrics_received)
    finally:
        try:
            rabbit_conn.close()
        except Exception:
            pass


def run() -> None:
    """Función principal que inicia el servicio"""
    # Inicializar base de datos
    init_database()
    
    # Iniciar consumidor de RabbitMQ
    start_consumer()


if __name__ == "__main__":
    run()
