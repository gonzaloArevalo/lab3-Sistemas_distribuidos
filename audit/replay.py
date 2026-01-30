import json
import time
import pika
import argparse
import os
from datetime import datetime
import settings

def connect():
    """Conexión usando las variables de settings.py"""
    params = pika.ConnectionParameters(
        host=settings.RABBIT_HOST,
        port=settings.RABBIT_PORT
    )
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel

def replay_events(start_line=0, start_time_iso=None, target_exchange=None):
    # 1. Usamos la ruta definida en tu settings.py
    log_path = settings.LOG_FILE_PATH
    
    if not os.path.exists(log_path):
        print(f"[!] ERROR: No existe el archivo de log en: {log_path}")
        print("    ¿Has generado tráfico primero? (run_load.sh / run_burst.sh)")
        return

    # Si no nos dicen a dónde enviar, usamos el mismo exchange que auditamos
    # (Esto hará que el Aggregator vuelva a recibir los mensajes)
    exchange_to_publish = target_exchange if target_exchange else settings.TARGET_EXCHANGE

    connection, channel = connect()
    
    print(f"[*] INICIANDO REPLAY")
    print(f"    -> Fuente: {log_path}")
    print(f"    -> Destino (Exchange): {exchange_to_publish}")
    print(f"    -> Offset (Línea): >= {start_line}")
    print(f"    -> Filtro Tiempo: >= {start_time_iso if start_time_iso else 'Todo el historial'}")
    print("-" * 50)

    replayed_count = 0
    skipped_count = 0
    
    # Preparamos filtro de fecha
    start_dt = None
    if start_time_iso:
        try:
            start_dt = datetime.fromisoformat(start_time_iso)
        except ValueError:
            print("[!] Error: Formato de fecha inválido. Usa formato ISO (ej: 2026-01-30T10:00:00)")
            return

    try:
        with open(log_path, 'r') as f:
            for index, line in enumerate(f):
                # --- LÓGICA DE REPLAY (Cumple Requisitos) ---

                # 1. Filtro por Offset (Posición/Línea)
                if index < start_line:
                    continue

                try:
                    event = json.loads(line)
                    
                    # 2. Filtro por Tiempo (Point-in-time recovery)
                    if start_dt:
                        # Buscamos el timestamp dentro del evento o del log
                        # Asumimos que tu log tiene un campo "timestamp" o el evento lo tiene
                        ts_str = event.get('timestamp') or event.get('original_event', {}).get('timestamp')
                        
                        if ts_str:
                            try:
                                # A veces vienen con milisegundos, cortamos lo extra si falla
                                event_dt = datetime.fromisoformat(ts_str)
                                if event_dt < start_dt:
                                    skipped_count += 1
                                    continue
                            except ValueError:
                                pass # Si no podemos parsear la fecha, lo enviamos igual por seguridad

                    # 3. Re-inyección (Publicar)
                    # Usamos el routing_key original para que llegue a la cola correcta (norte/sur/etc)
                    routing_key = event.get('routing_key', 'replay.unknown')
                    
                    # Limpieza: Si el log tiene metadatos extra del audit, enviamos solo el evento original
                    # Si tu log guarda el evento tal cual, enviamos 'event'.
                    payload = event.get('original_event', event) 

                    channel.basic_publish(
                        exchange=exchange_to_publish,
                        routing_key=routing_key,
                        body=json.dumps(payload),
                        properties=pika.BasicProperties(
                            delivery_mode=2, 
                            headers={"x-replay": "true"} # Marcamos que es un replay (opcional pero pro)
                        )
                    )
                    
                    replayed_count += 1
                    # Pequeño sleep para efecto visual en la demo
                    time.sleep(0.05) 
                    print(f" [Replay] Línea {index} -> Enviado a {routing_key}")

                except json.JSONDecodeError:
                    print(f" [!] Línea {index} corrupta, ignorando.")

    except KeyboardInterrupt:
        print("\n[!] Replay detenido por el usuario.")
    finally:
        connection.close()
        print("-" * 50)
        print(f"RESUMEN: Reinyectados: {replayed_count} | Omitidos por fecha: {skipped_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Herramienta de Replay de Eventos')
    parser.add_argument('--offset', type=int, default=0, help='Saltar las primeras N líneas (Offset)')
    parser.add_argument('--timestamp', type=str, default=None, help='Fecha ISO de inicio (YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('--exchange', type=str, default=None, help='Exchange destino (Opcional)')
    
    args = parser.parse_args()
    
    replay_events(
        start_line=args.offset, 
        start_time_iso=args.timestamp,
        target_exchange=args.exchange
    )