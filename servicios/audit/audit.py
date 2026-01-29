"""
Audit Service - Lab 3 País X.
Persiste la trazabilidad de eventos (qué eventos de entrada contribuyeron a qué métricas de salida).
Consume eventos validados y métricas generadas, almacenando en SQLite.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

import pika

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
EXCHANGE = "events_topic"
DB_PATH = os.getenv("DB_PATH", "/app/audit.db")

# Colas y routing keys
VALIDATED_TOPICS = ["validated.security.incident", "validated.survey.victimization", "validated.migration.case"]
METRICS_TOPIC = "metrics.daily"
QUEUE_AUDIT = "audit_queue"
FLUSH_INTERVAL_SECONDS = 30


def log_json(level: str, msg: str, **kwargs: Any) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "level": level,
        "service": "audit",
        "message": msg,
        **kwargs,
    }
    logger.info(json.dumps(entry))


def init_database() -> sqlite3.Connection:
    """Inicializa la base de datos SQLite con el esquema requerido"""
    conn = sqlite3.connect(DB_PATH)
    
    # Tabla de eventos de entrada
    conn.execute("""
        CREATE TABLE IF NOT EXISTS input_events (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            region TEXT NOT NULL,
            source TEXT NOT NULL,
            payload TEXT NOT NULL,
            received_at TEXT NOT NULL
        )
    """)
    
    # Tabla de métricas de salida
    conn.execute("""
        CREATE TABLE IF NOT EXISTS output_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            region TEXT NOT NULL,
            metrics TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(date, region)
        )
    """)
    
    # Tabla de trazabilidad
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_traceability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            metric_id INTEGER NOT NULL,
            contribution_type TEXT NOT NULL,
            traced_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES input_events (event_id),
            FOREIGN KEY (metric_id) REFERENCES output_metrics (metric_id)
        )
    """)
    
    # Índices para mejor rendimiento
    conn.execute("CREATE INDEX IF NOT EXISTS idx_input_events_region ON input_events (region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_input_events_source ON input_events (source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_output_metrics_date_region ON output_metrics (date, region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traceability_event_id ON event_traceability (event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traceability_metric_id ON event_traceability (metric_id)")
    
    conn.commit()
    log_json("INFO", "Base de datos inicializada", db_path=DB_PATH)
    return conn


def store_input_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    """Almacena un evento de entrada en la base de datos"""
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO input_events 
            (event_id, timestamp, region, source, payload, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("event_id"),
                event.get("timestamp"),
                event.get("region"),
                event.get("source"),
                json.dumps(event.get("payload", {})),
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        log_json("ERROR", "Error almacenando evento de entrada", error=str(e), event_id=event.get("event_id"))


def store_output_metric(conn: sqlite3.Connection, metric: dict[str, Any]) -> int:
    """Almacena una métrica de salida y retorna su ID"""
    try:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO output_metrics 
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
        return cursor.lastrowid
    except sqlite3.Error as e:
        log_json("ERROR", "Error almacenando métrica de salida", error=str(e), date=metric.get("date"), region=metric.get("region"))
        return -1


def link_event_to_metric(conn: sqlite3.Connection, event_id: str, metric_id: int, contribution_type: str) -> None:
    """Crea la relación de trazabilidad entre evento y métrica"""
    try:
        conn.execute(
            """
            INSERT INTO event_traceability 
            (event_id, metric_id, contribution_type, traced_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                metric_id,
                contribution_type,
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        log_json("ERROR", "Error creando trazabilidad", error=str(e), event_id=event_id, metric_id=metric_id)


def get_events_for_metric(conn: sqlite3.Connection, date: str, region: str) -> list[dict[str, Any]]:
    """Consulta qué eventos contribuyeron a una métrica específica"""
    try:
        cursor = conn.execute("""
            SELECT ie.event_id, ie.timestamp, ie.region, ie.source, ie.payload
            FROM input_events ie
            JOIN event_traceability et ON ie.event_id = et.event_id
            JOIN output_metrics om ON et.metric_id = om.metric_id
            WHERE om.date = ? AND om.region = ?
            ORDER BY ie.timestamp
        """, (date, region))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                "event_id": row[0],
                "timestamp": row[1],
                "region": row[2],
                "source": row[3],
                "payload": json.loads(row[4])
            })
        
        return events
    except sqlite3.Error as e:
        log_json("ERROR", "Error consultando eventos para métrica", error=str(e), date=date, region=region)
        return []


def run() -> None:
    # Inicializar base de datos
    conn = init_database()
    
    # Contadores
    input_events_processed = 0
    metrics_processed = 0
    traceability_links = 0
    last_flush = time.monotonic()
    
    # Conexión a RabbitMQ
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
                log_json("WARNING", "Error conectando a RabbitMQ, reintentando", error=str(e), attempt=attempt + 1, max_retries=max_retries)
                time.sleep(retry_delay)
            else:
                log_json("ERROR", "No se pudo conectar a RabbitMQ", error=str(e))
                raise

    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(QUEUE_AUDIT, durable=True)
    
    # Bind a todos los topics de interés
    for topic in VALIDATED_TOPICS:
        ch.queue_bind(queue=QUEUE_AUDIT, exchange=EXCHANGE, routing_key=topic)
    ch.queue_bind(queue=QUEUE_AUDIT, exchange=EXCHANGE, routing_key=METRICS_TOPIC)
    
    ch.basic_qos(prefetch_count=1)

    def on_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> None:
        nonlocal input_events_processed, metrics_processed, traceability_links, last_flush
        routing_key = method.routing_key
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            log_json("ERROR", "JSON inválido", error=str(e), routing_key=routing_key)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            if routing_key in VALIDATED_TOPICS:
                # Es un evento validado, almacenar como entrada
                store_input_event(conn, data)
                input_events_processed += 1
                
                log_json("DEBUG", "Evento de entrada almacenado", 
                        event_id=data.get("event_id"), 
                        source=data.get("source"),
                        input_count=input_events_processed)
                
            elif routing_key == METRICS_TOPIC:
                # Es una métrica generada, almacenar como salida
                metric_id = store_output_metric(conn, data)
                if metric_id > 0:
                    metrics_processed += 1
                    
                    # Para esta implementación simple, asumimos que todos los eventos
                    # del día y región contribuyeron a esta métrica
                    events = get_events_for_metric(conn, data.get("date"), data.get("region"))
                    for event in events:
                        link_event_to_metric(conn, event["event_id"], metric_id, "aggregation")
                        traceability_links += 1
                    
                    log_json("DEBUG", "Métrica de salida almacenada", 
                            date=data.get("date"), 
                            region=data.get("region"),
                            metric_id=metric_id,
                            events_linked=len(events),
                            metrics_count=metrics_processed)
            
            # Estadísticas periódicas
            if time.monotonic() - last_flush >= FLUSH_INTERVAL_SECONDS:
                log_json(
                    "INFO",
                    "Estadísticas de auditoría",
                    input_events=input_events_processed,
                    metrics_processed=metrics_processed,
                    traceability_links=traceability_links,
                    uptime_seconds=int(time.monotonic() - (time.monotonic() - FLUSH_INTERVAL_SECONDS))
                )
                last_flush = time.monotonic()

        except Exception as e:
            log_json("ERROR", "Error procesando mensaje", error=str(e), routing_key=routing_key)

        channel.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=QUEUE_AUDIT, on_message_callback=on_message)
    log_json("INFO", "Audit service iniciado", queue=QUEUE_AUDIT, topics=VALIDATED_TOPICS + [METRICS_TOPIC])

    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        log_json(
            "INFO", 
            "Audit service detenido", 
            input_events=input_events_processed,
            metrics_processed=metrics_processed,
            traceability_links=traceability_links
        )
    finally:
        try:
            rabbit_conn.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()