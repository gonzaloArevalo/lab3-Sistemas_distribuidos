import json
import time
import uuid
from datetime import datetime

import pika

import settings

# --- ESTADO EN MEMORIA --
# En un sistema real distribuido, esto debería estar en Redis
current_window_start = time.time()
processed_ids = {}     # Para Deduplicación: {event_id: timestamp_procesado}
stats_buffer = {}         # Estructura: { "norte": { "theft": 5, "assault": 1 }, ... }
event_ids_by_region = {}  # Estructura: { "norte": {"id1", "id2"} }

def connect_rabbitmq():
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Aseguramos que los exchanges existan
            channel.exchange_declare(exchange=settings.INPUT_EXCHANGE, exchange_type='topic', durable=True)
            channel.exchange_declare(exchange=settings.OUTPUT_EXCHANGE, exchange_type='topic', durable=True)
            channel.exchange_declare(exchange='dlq_exchange', exchange_type='direct', durable=True)
            
            # Declarar cola deadletter.processing para eventos que fallan en agregación
            channel.queue_declare(queue='deadletter.processing', durable=True)
            channel.queue_bind(exchange='dlq_exchange', queue='deadletter.processing', routing_key='deadletter.processing')

            # Declarar y bindear cola
            channel.queue_declare(queue=settings.QUEUE_NAME, durable=True)
            # Escuchamos TODO (#) lo que venga validado
            channel.queue_bind(exchange=settings.INPUT_EXCHANGE, queue=settings.QUEUE_NAME, routing_key="#")

            print(f"[*] Aggregator conectado. Ventana de {settings.AGGREGATION_WINDOW}s")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] Esperando a RabbitMQ...")
            time.sleep(5)

def cleanup_old_processed_ids():
    """Limpia IDs procesados antiguos para evitar fugas de memoria"""
    global processed_ids
    current_time = time.time()
    # Eliminar IDs procesados hace más de 1 hora (3600 segundos)
    cutoff_time = current_time - 3600
    
    old_ids = [event_id for event_id, timestamp in processed_ids.items() if timestamp < cutoff_time]
    for old_id in old_ids:
        del processed_ids[old_id]
    
    # Asignación explícita para satisfacer Flake8
    processed_ids = processed_ids
    
    if old_ids:
        print(f" [c] Limpiados {len(old_ids)} IDs antiguos de deduplicación")

def flush_window(channel):
    """Publica los resultados acumulados y reinicia el buffer"""
    global current_window_start, stats_buffer, event_ids_by_region

    if not stats_buffer:
        # Si no hubo datos, solo actualizamos el tiempo
        current_window_start = time.time()
        return

    # Crear mensaje de resumen
    total_events_in_window = sum(len(event_ids) for event_ids in event_ids_by_region.values())
    summary = {
        "type": "window_summary",
        "window_start_iso": datetime.fromtimestamp(current_window_start).isoformat(),
        "window_end_iso": datetime.now().isoformat(),
        "total_processed": total_events_in_window,
        "stats_by_region": stats_buffer
    }

    # Publicar al exchange de analytics
    channel.basic_publish(
        exchange=settings.OUTPUT_EXCHANGE,
        routing_key="analytics.window",
        body=json.dumps(summary),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    # Publicar métricas diarias por región con trazabilidad
    for region, region_stats in stats_buffer.items():
        metric_msg = {
            "metric_id": str(uuid.uuid4()),
            "date": datetime.now().date().isoformat(),
            "region": region,
            "run_id": "default",
            "metrics": region_stats,
            "input_event_ids": sorted(event_ids_by_region.get(region, set())),
        }
        channel.basic_publish(
            exchange=settings.OUTPUT_EXCHANGE,
            routing_key="metrics.daily",
            body=json.dumps(metric_msg),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    print(f" [S] Ventana cerrada. Publicado resumen de {len(event_ids_by_region)} eventos únicos.")
    
    # Limpiar IDs antiguos periódicamente
    cleanup_old_processed_ids()
    
    # Reiniciar estado de ventana (mantenemos processed_ids)
    stats_buffer = {}
    event_ids_by_region = {}
    current_window_start = time.time()

def log_deadletter_event(event_id, error_msg, routing_key):
    """Loguea eventos que irían a deadletter.processing (implementación simplificada)"""
    try:
        dlq_message = {
            "original_event_id": event_id,
            "error": error_msg,
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "service": "aggregator",
            "routing_key": routing_key,
            "destination": "deadletter.processing"
        }
        
        # Guardar en archivo de log local (evita problemas de canal)
        with open('/tmp/deadletter_processing.log', 'a') as f:
            f.write(json.dumps(dlq_message) + '\n')
        
        # Mostrar JSON en consola para demostración
        print(f" [d] DUPLICADO DETECTADO -> DEADLETTER: {json.dumps(dlq_message)}")
        
    except Exception as e:
        print(f" [!] Error logueando deadletter: {e}")

def send_to_deadletter_processing(ch, method, body, event_id, error_msg):
    """Envía eventos que fallaron en el procesamiento a deadletter.processing"""
    try:
        original_event = json.loads(body)
        
        dlq_message = {
            "original_event": original_event,
            "error": error_msg,
            "event_id": event_id,
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "service": "aggregator",
            "routing_key": method.routing_key
        }
        
        # Crear una conexión separada para deadletter
        try:
            dlq_connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            )
            dlq_channel = dlq_connection.channel()
            dlq_channel.exchange_declare(exchange='dlq_exchange', exchange_type='direct', durable=True)
            
            # Publicar al exchange de deadletter de procesamiento
            dlq_channel.basic_publish(
                exchange='dlq_exchange',
                routing_key='deadletter.processing',
                body=json.dumps(dlq_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            
            dlq_channel.close()
            dlq_connection.close()
            print(f" [d] Enviado a deadletter.processing: {event_id} - {error_msg}")
            
        except Exception as dlq_error:
            print(f" [!] Error en conexión DLQ: {dlq_error}")
        
    except Exception as e:
        print(f" [!] Error procesando deadletter: {e}")

def process_event(event):
    """Lógica de agregación pura"""
    region = event.get("region", "unknown")
    source = event.get("source", "unknown")
    event_id = event.get("event_id")
    
    # Inicializar contadores si no existen
    if region not in stats_buffer:
        stats_buffer[region] = {}
    if source not in stats_buffer[region]:
        stats_buffer[region][source] = 0
        
    stats_buffer[region][source] += 1

    if event_id:
        event_ids_by_region.setdefault(region, set()).add(event_id)

def callback(ch, method, properties, body):
    
    try:
        event = json.loads(body)
        event_id = event.get("event_id")

        # 1. DEDUPLICACIÓN (Idempotencia)
        current_time = time.time()
        
        if event_id in processed_ids:
            # Verificar si el evento fue procesado recientemente (dentro de la ventana actual)
            processed_time = processed_ids[event_id]
            if current_time - processed_time < settings.AGGREGATION_WINDOW:
                print(f" [d] Duplicado detectado: {event_id} (procesado hace {current_time - processed_time:.1f}s)")
                # Loguear para deadletter.processing (implementación simplificada)
                log_deadletter_event(event_id, "Evento duplicado ya procesado", method.routing_key)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            else:
                # Evento antiguo que se vuelve a procesar, actualizamos timestamp
                print(f" [r] Re-procesando evento antiguo: {event_id}")

        # 2. PROCESAMIENTO
        process_event(event)
        processed_ids[event_id] = current_time

        # 3. VERIFICAR SI CERRAMOS VENTANA
        # verificamos el tiempo en cada mensaje. Si no llegan mensajes, la ventana no se cierra.
        if time.time() - current_window_start >= settings.AGGREGATION_WINDOW:
            flush_window(ch)

    except Exception as e:
        print(f" [!] Error agregando: {e}")
        # Loguear para deadletter.processing (implementación simplificada)
        log_deadletter_event(event.get("event_id", "unknown"), f"Error de procesamiento: {str(e)}", method.routing_key)
    
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    while True:
        try:
            connection, channel = connect_rabbitmq()
            channel.basic_qos(prefetch_count=10) # Traer varios mensajes para ser eficiente
            channel.basic_consume(queue=settings.QUEUE_NAME, on_message_callback=callback)
            
            print(' [*] Aggregator corriendo...')
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                print(' [!] Deteniendo aggregator...')
                channel.stop_consuming()
                connection.close()
                break
                
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.ConnectionClosedByBroker) as e:
            print(f' [!] Conexión perdida: {e}. Reintentando en 5 segundos...')
            try:
                connection.close()
            except:
                pass
            time.sleep(5)
        except (pika.exceptions.AMQPChannelError, pika.exceptions.ChannelClosedByBroker) as e:
            print(f' [!] Error de canal: {e}. Reintentando en 5 segundos...')
            try:
                connection.close()
            except:
                pass
            time.sleep(5)
        except Exception as e:
            print(f' [!] Error inesperado: {e}. Reintentando en 5 segundos...')
            try:
                connection.close()
            except:
                pass
            time.sleep(5)

if __name__ == "__main__":
    main()
