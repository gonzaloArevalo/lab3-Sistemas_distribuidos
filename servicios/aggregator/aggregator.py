"""
Aggregator - Lab 3 País X.
Consume eventos validados de aggregator_queue, deduplica por event_id,
agrega por ventanas diarias por región (UTC), publica en metrics.daily.
Eventos que fallan → deadletter.processing.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import pika

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
EXCHANGE = "events_topic"
QUEUE_AGGREGATOR = "aggregator_queue"
QUEUE_DEADLETTER_PROC = "deadletter.processing"
QUEUE_METRICS_DAILY = "metrics_daily_queue"
ROUTING_METRICS = "metrics.daily"
DEDUP_TTL_SECONDS = 86400 * 2  # 2 días
FLUSH_INTERVAL_SECONDS = 60
SEEN_MAX = 100_000


def log_json(level: str, msg: str, **kwargs: Any) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "level": level,
        "service": "aggregator",
        "message": msg,
        **kwargs,
    }
    logger.info(json.dumps(entry))


def date_utc(ts: str) -> str | None:
    """Extrae fecha YYYY-MM-DD en UTC del timestamp ISO."""
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.strftime("%Y-%m-%d")
    except Exception:
        return None


def update_metrics(bucket: dict[str, Any], source: str, payload: dict, region: str) -> None:
    if source == "security.incident":
        b = bucket.setdefault("security.incident", {"count": 0, "by_severity": defaultdict(int), "by_crime_type": defaultdict(int)})
        b["count"] += 1
        b["by_severity"][payload.get("severity", "unknown")] += 1
        b["by_crime_type"][payload.get("crime_type", "other")] += 1
    elif source == "survey.victimization":
        b = bucket.setdefault("survey.victimization", {"count": 0, "reported_count": 0})
        b["count"] += 1
        if payload.get("reported"):
            b["reported_count"] += 1
    elif source == "migration.case":
        b = bucket.setdefault("migration.case", {"count": 0, "by_status": defaultdict(int)})
        b["count"] += 1
        b["by_status"][payload.get("status", "unknown")] += 1


def build_metrics_payload(date: str, region: str, raw: dict[str, Any]) -> dict[str, Any]:
    m = raw.get("metrics", {})
    out = {"date": date, "region": region, "metrics": {}}
    if "security.incident" in m:
        s = m["security.incident"]
        out["metrics"]["security.incident"] = {
            "count": s["count"],
            "by_severity": dict(s["by_severity"]),
            "by_crime_type": dict(s["by_crime_type"]),
        }
    if "survey.victimization" in m:
        s = m["survey.victimization"]
        r = s["reported_count"] / s["count"] if s["count"] else 0
        out["metrics"]["survey.victimization"] = {"count": s["count"], "reported_rate": round(r, 2)}
    if "migration.case" in m:
        s = m["migration.case"]
        out["metrics"]["migration.case"] = {"count": s["count"], "by_status": dict(s["by_status"])}
    return out


def run() -> None:
    seen: dict[str, float] = {} # ventana con ids
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"metrics": {}}) # diccionario con las metricas
    processed = 0
    duplicates = 0
    last_flush = time.monotonic()

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
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                log_json("WARNING", "Error conectando a RabbitMQ, reintentando", error=str(e), attempt=attempt + 1, max_retries=max_retries)
                time.sleep(retry_delay)
            else:
                log_json("ERROR", "No se pudo conectar a RabbitMQ", error=str(e))
                raise

    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(QUEUE_AGGREGATOR, durable=True)
    ch.queue_declare(QUEUE_DEADLETTER_PROC, durable=True)
    ch.queue_declare(QUEUE_METRICS_DAILY, durable=True)
    
    # Bind aggregator_queue a eventos validados
    ch.queue_bind(queue=QUEUE_AGGREGATOR, exchange=EXCHANGE, routing_key="validated.security.incident")
    ch.queue_bind(queue=QUEUE_AGGREGATOR, exchange=EXCHANGE, routing_key="validated.survey.victimization")
    ch.queue_bind(queue=QUEUE_AGGREGATOR, exchange=EXCHANGE, routing_key="validated.migration.case")
    
    ch.queue_bind(queue=QUEUE_METRICS_DAILY, exchange=EXCHANGE, routing_key=ROUTING_METRICS)
    ch.basic_qos(prefetch_count=1)

    def evict_seen() -> None:
        now = time.time()
        to_del = [eid for eid, t in seen.items() if now - t > DEDUP_TTL_SECONDS]
        for eid in to_del:
            del seen[eid]
        while len(seen) > SEEN_MAX:
            oldest = min(seen, key=seen.get)
            del seen[oldest]

    def flush_pending(force_all: bool = False) -> None:
        now_utc = datetime.now(timezone.utc)
        today = now_utc.strftime("%Y-%m-%d")
        to_flush = [(d, r) for (d, r) in list(buckets.keys()) if force_all or d < today]
        for (d, r) in to_flush:
            key = (d, r)
            raw = buckets.pop(key, None)
            if not raw:
                continue
            payload = build_metrics_payload(d, r, raw)
            body = json.dumps(payload)
            ch.basic_publish(
                exchange=EXCHANGE,
                routing_key=ROUTING_METRICS,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )
            log_json("INFO", "Métricas publicadas", date=d, region=r, routing_key=ROUTING_METRICS)

    def on_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> None:
        nonlocal processed, duplicates, last_flush
        try:
            ev = json.loads(body)
        except json.JSONDecodeError as e:
            dlq = {"error": f"JSON inválido: {e}", "body": body.decode("utf-8", errors="replace")}
            ch.basic_publish(exchange="", routing_key=QUEUE_DEADLETTER_PROC, body=json.dumps(dlq), properties=pika.BasicProperties(delivery_mode=2))
            log_json("WARNING", "Evento a deadletter.processing (JSON inválido)", error=str(e))
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        eid = ev.get("event_id")
        if not eid:
            dlq = {"error": "event_id faltante", "original_event": ev}
            ch.basic_publish(exchange="", routing_key=QUEUE_DEADLETTER_PROC, body=json.dumps(dlq), properties=pika.BasicProperties(delivery_mode=2))
            log_json("WARNING", "Evento a deadletter.processing (sin event_id)")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        now = time.time()
        if eid in seen:
            duplicates += 1
            log_json("DEBUG", "Evento duplicado omitido", event_id=eid, duplicate_count=duplicates)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        seen[eid] = now
        evict_seen()

        ts = ev.get("timestamp")
        region = ev.get("region", "unknown")
        source = ev.get("source")
        payload = ev.get("payload") or {}
        d = date_utc(ts) if ts else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not d:
            dlq = {"error": "timestamp inválido", "original_event": ev}
            ch.basic_publish(exchange="", routing_key=QUEUE_DEADLETTER_PROC, body=json.dumps(dlq), properties=pika.BasicProperties(delivery_mode=2))
            log_json("WARNING", "Evento a deadletter.processing (timestamp inválido)", event_id=eid)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            key = (d, region)
            update_metrics(buckets[key]["metrics"], source, payload, region)
        except Exception as e:
            dlq = {"error": str(e), "original_event": ev}
            ch.basic_publish(exchange="", routing_key=QUEUE_DEADLETTER_PROC, body=json.dumps(dlq), properties=pika.BasicProperties(delivery_mode=2))
            log_json("WARNING", "Evento a deadletter.processing (agregación)", error=str(e), event_id=eid)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        processed += 1
        if processed % 500 == 0:
            log_json("INFO", "Eventos agregados", processed=processed, duplicates=duplicates, buckets=len(buckets))

        if time.monotonic() - last_flush >= FLUSH_INTERVAL_SECONDS:
            flush_pending()
            last_flush = time.monotonic()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=QUEUE_AGGREGATOR, on_message_callback=on_message)
    log_json("INFO", "Aggregator consumiendo", queue=QUEUE_AGGREGATOR)

    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        flush_pending(force_all=True)
        log_json("INFO", "Aggregator detenido", processed=processed, duplicates=duplicates)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()
