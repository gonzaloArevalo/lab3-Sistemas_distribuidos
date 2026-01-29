"""
Validador de eventos - Lab 3 País X.
Consume de security.incident, survey.victimization, migration.case;
valida esquema; envía válidos a validated.* e inválidos a deadletter.validation.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pika
from jsonschema import FormatChecker, ValidationError, validate

# Logging estructurado (JSON)
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
SCHEMA_FILE = os.getenv("SCHEMA_FILE", "/app/schemas/event_schema.json")
SCHEMA_DIR = os.getenv("SCHEMA_DIR", str(Path(SCHEMA_FILE).parent))

INPUT_TOPICS = ["security.incident", "survey.victimization", "migration.case"]
EXCHANGE = "events_topic"
QUEUE_VALIDATOR = "validator_queue"
QUEUE_AGGREGATOR = "aggregator_queue"
QUEUE_DEADLETTER = "deadletter.validation"
ROUTING_VALIDATED_PREFIX = "validated."
FORMAT_CHECKER = FormatChecker()


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schemas() -> tuple[dict, dict[str, dict]]:
    base = load_json(SCHEMA_FILE)
    payloads = {}
    for name, key in [
        ("payload_security_incident.json", "security.incident"),
        ("payload_survey_victimization.json", "survey.victimization"),
        ("payload_migration_case.json", "migration.case"),
    ]:
        p = Path(SCHEMA_DIR) / name
        if p.exists():
            payloads[key] = load_json(str(p))
        else:
            payloads[key] = {"type": "object"}  # fallback
    return base, payloads


def log_json(level: str, msg: str, **kwargs: Any) -> None:
    entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "level": level,
        "service": "validator",
        "message": msg,
        **kwargs,
    }
    logger.info(json.dumps(entry))


def validate_event(
    data: dict,
    routing_key: str,
    base_schema: dict,
    payload_schemas: dict[str, dict],
) -> str | None:
    """Valida evento. Retorna None si OK, sino mensaje de error."""
    # Validar estructura base del JSON
    try:
        validate(data, base_schema, format_checker=FORMAT_CHECKER)
    except ValidationError as e:
        return f"schema base: {e!s}"

    # Validar source correspondiende al topic
    source = data.get("source")
    if source != routing_key:
        return f"source '{source}' no coincide con tópico '{routing_key}'"

    
    # Validar payload
    schema = payload_schemas.get(routing_key)
    if not schema:
        return f"schema de payload desconocido para '{routing_key}'"

    try:
        validate(data.get("payload", {}), schema, format_checker=FORMAT_CHECKER)
    except ValidationError as e:
        return f"payload ({routing_key}): {e!s}"

    return None


def run() -> None:
    base_schema, payload_schemas = load_schemas()
    log_json("INFO", "Schemas cargados", schema_file=SCHEMA_FILE, schema_dir=SCHEMA_DIR)

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
                log_json(
                    "WARNING",
                    "Error conectando a RabbitMQ, reintentando",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                time.sleep(retry_delay)
            else:
                log_json(
                    "ERROR",
                    "No se pudo conectar a RabbitMQ",
                    error=str(e),
                )
                raise

    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(QUEUE_VALIDATOR, durable=True)
    ch.queue_declare(QUEUE_AGGREGATOR, durable=True)
    ch.queue_declare(QUEUE_DEADLETTER, durable=True)

    for rk in INPUT_TOPICS:
        ch.queue_bind(queue=QUEUE_VALIDATOR, exchange=EXCHANGE, routing_key=rk)
    for rk in INPUT_TOPICS:
        ch.queue_bind(
            queue=QUEUE_AGGREGATOR,
            exchange=EXCHANGE,
            routing_key=ROUTING_VALIDATED_PREFIX + rk,
        )

    ch.basic_qos(prefetch_count=1)
    validated = 0
    invalid = 0

    def on_message(channel, method, properties, body):
        nonlocal validated, invalid
        routing_key = method.routing_key

        try:
            raw = json.loads(body)
        except json.JSONDecodeError as e:
            invalid += 1
            dlq_payload = {
                "original_body": body.decode("utf-8", errors="replace"),
                "error": f"JSON inválido: {e}",
                "routing_key": routing_key,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            ch.basic_publish(
                exchange="",
                routing_key=QUEUE_DEADLETTER,
                body=json.dumps(dlq_payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            log_json(
                "WARNING",
                "Evento rechazado (JSON inválido) → deadletter",
                error=str(e),
                routing_key=routing_key,
                invalid_count=invalid,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        err = validate_event(raw, routing_key, base_schema, payload_schemas)
        if err:
            invalid += 1
            dlq_payload = {
                "original_event": raw,
                "error": err,
                "routing_key": routing_key,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            ch.basic_publish(
                exchange="",
                routing_key=QUEUE_DEADLETTER,
                body=json.dumps(dlq_payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            log_json(
                "WARNING",
                "Evento rechazado (validación) → deadletter",
                error=err,
                event_id=raw.get("event_id"),
                routing_key=routing_key,
                invalid_count=invalid,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Válido → publicar en validated.<source>
        out_rk = ROUTING_VALIDATED_PREFIX + raw["source"]
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key=out_rk,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=raw.get("event_id"),
                headers={
                    "region": raw.get("region"),
                    "source": raw.get("source"),
                    "schema_version": raw.get("schema_version"),
                },
            ),
        )
        validated += 1
        log_json(
            "INFO",
            "Evento válido reenviado",
            event_id=raw.get("event_id"),
            routing_key=routing_key,
            validated_count=validated,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    # Consumir mensajes de la cola para el validator
    ch.basic_consume(queue=QUEUE_VALIDATOR, on_message_callback=on_message)
    log_json("INFO", "Validator consumiendo", queue=QUEUE_VALIDATOR, topics=INPUT_TOPICS)

    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        log_json("INFO", "Validator detenido", validated=validated, invalid=invalid)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()
