import pika
import json
import uuid
import time
import os
import random
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configuración de logging estructurado (JSON)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
TOPICS = ['security.incident', 'survey.victimization', 'migration.case']
REGIONS = ['norte', 'sur', 'centro', 'este', 'oeste']

# Tipos de delitos y severidades
CRIME_TYPES = ['theft', 'assault', 'burglary', 'vandalism', 'fraud', 'other']
SEVERITIES = ['low', 'medium', 'high']

# Tipos de victimización
VICTIMIZATION_TYPES = ['property_crime', 'violent_crime', 'cyber_crime', 'other']

# Tipos de casos de migración
MIGRATION_CASE_TYPES = ['asylum', 'refugee', 'work_visa', 'family_reunion', 'other']
MIGRATION_STATUSES = ['pending', 'approved', 'rejected', 'in_review']


def create_security_incident_payload(region: str, rng: random.Random) -> Dict[str, Any]:
    """Crea payload para evento security.incident"""
    return {
        "crime_type": rng.choice(CRIME_TYPES),
        "severity": rng.choice(SEVERITIES),
        "location": {
            "latitude": round(rng.uniform(-33.5, -33.4), 4),
            "longitude": round(rng.uniform(-70.7, -70.6), 4)
        },
        "reported_by": rng.choice(["citizen", "police", "security_system", "other"])
    }


def create_survey_victimization_payload(region: str, rng: random.Random) -> Dict[str, Any]:
    """Crea payload para evento survey.victimization"""
    return {
        "survey_id": f"survey-2025-{rng.randint(1, 999):03d}",
        "respondent_age": rng.randint(18, 80),
        "victimization_type": rng.choice(VICTIMIZATION_TYPES),
        "incident_date": (datetime.utcnow() - timedelta(days=rng.randint(0, 365))).strftime("%Y-%m-%d"),
        "reported": rng.choice([True, False])
    }


def create_migration_case_payload(region: str, rng: random.Random) -> Dict[str, Any]:
    """Crea payload para evento migration.case"""
    return {
        "case_id": f"mig-2025-{rng.randint(1, 999):03d}",
        "case_type": rng.choice(MIGRATION_CASE_TYPES),
        "status": rng.choice(MIGRATION_STATUSES),
        "origin_country": f"country-{rng.choice(['x', 'y', 'z'])}",
        "application_date": (datetime.utcnow() - timedelta(days=rng.randint(0, 180))).strftime("%Y-%m-%d")
    }


def create_event(source: str, region: Optional[str] = None, 
                 event_id: Optional[str] = None, 
                 timestamp: Optional[str] = None,
                 rng: random.Random = None) -> Dict[str, Any]:
    """Genera un evento"""
    if rng is None:
        rng = random
    
    if region is None:
        region = rng.choice(REGIONS)
    
    if event_id is None:
        event_id = str(uuid.uuid4())
    
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Crear payload específico según el tipo de evento
    payload_creators = {
        'security.incident': create_security_incident_payload,
        'survey.victimization': create_survey_victimization_payload,
        'migration.case': create_migration_case_payload
    }
    
    payload = payload_creators[source](region, rng)
    
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "region": region,
        "source": source,
        "schema_version": "1.0",
        "correlation_id": str(uuid.uuid4()),
        "payload": payload
    }


def log_structured(level: str, message: str, **kwargs):
    """Log estructurado en formato JSON"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "publisher",
        "message": message,
        **kwargs
    }
    logger.info(json.dumps(log_entry))


def run_publisher(mode: str = 'normal', rate: float = 1.0, 
                 seed: Optional[int] = None, duplicate_rate: float = 0.0,
                 out_of_order_rate: float = 0.0):
    """Ejecuta el publisher con diferentes modos de operación"""
    
    # Configurar seed para reproducibilidad
    if seed is not None:
        random.seed(seed)
        rng = random.Random(seed)
        log_structured("INFO", "Seed configurado para reproducibilidad", seed=seed)
    else:
        rng = random.Random()
    
    # Conexión al Broker con reintentos
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    connection_attempts=3,
                    retry_delay=2
                )
            )
            channel = connection.channel()
            
            # Declaración del Exchange tipo 'topic'
            channel.exchange_declare(exchange='events_topic', exchange_type='topic', durable=True)
            
            log_structured("INFO", "Publisher iniciado", 
                          mode=mode, rate=rate, host=RABBITMQ_HOST, port=RABBITMQ_PORT)
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                log_structured("WARNING", "Error conectando a RabbitMQ, reintentando", 
                              error=str(e), attempt=attempt+1, max_retries=max_retries)
                time.sleep(retry_delay)
            else:
                log_structured("ERROR", "No se pudo conectar a RabbitMQ después de múltiples intentos", 
                              error=str(e))
                raise
    
    # Variables para modos especiales
    event_counter = 0
    duplicate_counter = 0
    out_of_order_counter = 0
    last_timestamp = datetime.utcnow()
    
    # Cache de eventos para duplicados
    recent_events = []
    
    try:
        while True:
            # Seleccionar tópico
            topic = rng.choice(TOPICS)
            region = rng.choice(REGIONS)
            
            # Generar evento base
            event_id = str(uuid.uuid4())
            timestamp = datetime.utcnow()
            
            # Modo: Duplicados controlados
            if mode == 'duplicates' or (mode == 'normal' and rng.random() < duplicate_rate):
                if recent_events:
                    # Reutilizar un evento reciente
                    original_event = rng.choice(recent_events)
                    event_id = original_event['event_id']
                    timestamp = original_event['timestamp']
                    region = original_event['region']
                    topic = original_event['source']
                    duplicate_counter += 1
                    log_structured("INFO", "Evento duplicado generado", 
                                  event_id=event_id, duplicate_count=duplicate_counter)
            
            # Modo: Out-of-order
            if mode == 'out-of-order' or (mode == 'normal' and rng.random() < out_of_order_rate):
                # Generar timestamp en el pasado o futuro
                if rng.random() < 0.5:
                    # Timestamp en el pasado (hasta 1 hora)
                    timestamp = last_timestamp - timedelta(seconds=rng.randint(1, 3600))
                else:
                    # Timestamp en el futuro (hasta 5 minutos)
                    timestamp = last_timestamp + timedelta(seconds=rng.randint(1, 300))
                out_of_order_counter += 1
                log_structured("INFO", "Evento out-of-order generado", 
                              timestamp=timestamp.isoformat() + "Z", 
                              out_of_order_count=out_of_order_counter)
            
            # Crear evento
            event = create_event(
                source=topic,
                region=region,
                event_id=event_id,
                timestamp=timestamp.isoformat() + "Z",
                rng=rng
            )
            
            # Guardar evento reciente para duplicados
            recent_events.append({
                'event_id': event_id,
                'timestamp': timestamp,
                'region': region,
                'source': topic
            })
            if len(recent_events) > 100:  # Mantener solo los últimos 100
                recent_events.pop(0)
            
            # Publicar mensaje
            channel.basic_publish(
                exchange='events_topic',
                routing_key=topic,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistente (At-least-once)
                    message_id=event_id,
                    timestamp=int(timestamp.timestamp()),
                    headers={
                        'region': region,
                        'source': topic,
                        'schema_version': '1.0'
                    }
                )
            )
            
            event_counter += 1
            last_timestamp = timestamp
            
            log_structured("INFO", "Evento publicado", 
                         event_id=event_id, topic=topic, region=region, 
                         event_count=event_counter)
            
            # Modo: Burst
            if mode == 'burst':
                # Generar ráfaga de eventos
                burst_size = rng.randint(10, 50)
                for _ in range(burst_size - 1):
                    topic = rng.choice(TOPICS)
                    region = rng.choice(REGIONS)
                    event = create_event(source=topic, region=region, rng=rng)
                    channel.basic_publish(
                        exchange='events_topic',
                        routing_key=topic,
                        body=json.dumps(event),
                        properties=pika.BasicProperties(
                            delivery_mode=2,
                            message_id=event['event_id']
                        )
                    )
                    event_counter += 1
                    log_structured("INFO", "Evento de ráfaga publicado", 
                                 event_id=event['event_id'], topic=topic, 
                                 burst_size=burst_size, event_count=event_counter)
                
                # Esperar después de la ráfaga
                time.sleep(rng.uniform(5.0, 15.0))
            else:
                # Modo normal: tasa constante configurable
                time.sleep(1.0 / rate)
                
    except KeyboardInterrupt:
        log_structured("INFO", "Publisher detenido por usuario", 
                      total_events=event_counter, duplicates=duplicate_counter,
                      out_of_order=out_of_order_counter)
    except Exception as e:
        log_structured("ERROR", "Error en publisher", error=str(e))
        raise
    finally:
        try:
            connection.close()
            log_structured("INFO", "Conexión cerrada")
        except:
            pass


def main():
    parser = argparse.ArgumentParser(
        description='Publisher/Generator de eventos para el sistema event-driven',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos de operación:
  normal        - Genera eventos a tasa constante (default)
  burst         - Genera picos de eventos para pruebas de backpressure
  duplicates    - Inyecta eventos duplicados (mismo event_id)
  out-of-order  - Publica eventos con timestamps fuera de orden

Ejemplos:
  python publisher.py --mode normal --rate 2.0
  python publisher.py --mode burst
  python publisher.py --mode normal --seed 42 --duplicate-rate 0.1
  python publisher.py --mode out-of-order
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['normal', 'burst', 'duplicates', 'out-of-order'],
        default='normal',
        help='Modo de operación del publisher (default: normal)'
    )
    
    parser.add_argument(
        '--rate',
        type=float,
        default=1.0,
        help='Tasa de eventos por segundo en modo normal (default: 1.0)'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Seed para reproducibilidad de eventos generados'
    )
    
    parser.add_argument(
        '--duplicate-rate',
        type=float,
        default=0.0,
        help='Tasa de eventos duplicados en modo normal (0.0-1.0, default: 0.0)'
    )
    
    parser.add_argument(
        '--out-of-order-rate',
        type=float,
        default=0.0,
        help='Tasa de eventos out-of-order en modo normal (0.0-1.0, default: 0.0)'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.rate <= 0:
        parser.error("--rate debe ser mayor que 0")
    if not 0 <= args.duplicate_rate <= 1:
        parser.error("--duplicate-rate debe estar entre 0.0 y 1.0")
    if not 0 <= args.out_of_order_rate <= 1:
        parser.error("--out-of-order-rate debe estar entre 0.0 y 1.0")
    
    run_publisher(
        mode=args.mode,
        rate=args.rate,
        seed=args.seed,
        duplicate_rate=args.duplicate_rate,
        out_of_order_rate=args.out_of_order_rate
    )


if __name__ == "__main__":
    main()
