import json
import uuid
import time
import random
import argparse
import pika
from datetime import datetime, timezone

# Configuración de RabbitMQ
RABBITMQ_HOST = 'rabbitmq'
EXCHANGE_NAME = 'events_exchange'

# Datos base para generación aleatoria
REGIONS = ["norte", "sur", "centro", "este", "oeste"]
CRIME_TYPES = ["theft", "assault", "burglary", "homicide"]
SEVERITIES = ["low", "medium", "high"]

def get_timestamp():
    """Retorna timestamp en ISO-8601 UTC [cite: 143]"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def generate_base_event(source_type, region=None):
    """Genera la estructura base obligatoria del JSON """
    if not region:
        region = random.choice(REGIONS)
    
    return {
        "event_id": str(uuid.uuid4()),     # [cite: 142]
        "timestamp": get_timestamp(),      # [cite: 143]
        "region": region,                  # [cite: 144]
        "source": source_type,             # [cite: 145]
        "schema_version": "1.0",           # [cite: 146]
        "correlation_id": f"corr-{random.randint(1000, 9999)}", # [cite: 147]
        "payload": {}                      # [cite: 148]
    }

# --- Generadores Específicos por Tipo [cite: 151-201] ---

def create_security_incident():
    event = generate_base_event("security.incident")
    event["payload"] = {
        "crime_type": random.choice(CRIME_TYPES),
        "severity": random.choice(SEVERITIES),
        "location": {
            "latitude": round(random.uniform(-55.0, -17.0), 4),
            "longitude": round(random.uniform(-75.0, -66.0), 4)
        },
        "reported_by": random.choice(["citizen", "police", "app"])
    }
    return event

def create_victimization_survey():
    event = generate_base_event("survey.victimization")
    event["payload"] = {
        "survey_id": f"srv-{random.randint(10000, 99999)}",
        "respondent_age": random.randint(18, 90),
        "victimization_type": random.choice(CRIME_TYPES),
        "incident_date": datetime.now().strftime("%Y-%m-%d"),
        "reported": random.choice([True, False])
    }
    return event

def create_migration_case():
    event = generate_base_event("migration.case")
    event["payload"] = {
        "case_id": f"mig-{random.randint(10000, 99999)}",
        "case_type": random.choice(["asylum", "visa", "residence"]),
        "status": random.choice(["pending", "approved", "rejected"]),
        "origin_country": f"country-{random.choice(['A', 'B', 'C'])}",
        "application_date": datetime.now().strftime("%Y-%m-%d")
    }
    return event

def connect_rabbitmq():
    """Conexión con reintentos básicos para esperar al contenedor de RabbitMQ"""
    while True:
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            # Declaramos un Topic Exchange duradero
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)
            print(f"[*] Conectado a RabbitMQ en '{RABBITMQ_HOST}'")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] Esperando a RabbitMQ en '{RABBITMQ_HOST}'...")
            time.sleep(5)

def main():
    # Argumentos para reproducibilidad y configuración [cite: 211, 212]
    parser = argparse.ArgumentParser(description='Generador de Eventos País X')
    parser.add_argument('--seed', type=int, default=None, help='Semilla para reproducibilidad')
    parser.add_argument('--interval', type=float, default=1.0, help='Segundos entre eventos')
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        print(f"[*] Usando seed: {args.seed}")

    connection, channel = connect_rabbitmq()

    try:
        while True:
            # Seleccionar aleatoriamente qué tipo de evento generar
            choice = random.choices(
                [create_security_incident, create_victimization_survey, create_migration_case],
                weights=[0.5, 0.3, 0.2] # Ejemplo: más delitos que migración
            )[0]
            
            event = choice()
            routing_key = event["source"] # security.incident, etc.
            
            # Publicar al exchange
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Mensaje persistente
                    content_type='application/json'
                )
            )
            
            print(f"[x] Enviado {routing_key}: {event['event_id']}")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("Deteniendo generador...")
        connection.close()

if __name__ == "__main__":
    main()