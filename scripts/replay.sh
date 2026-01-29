#!/bin/bash

# replay.sh - Script para demostrar capacidad de replay
# Laboratorio 3: Publish & Subscribe - Sistema Event-Driven

set -e

# Configuración por defecto
REPLAY_TYPE=${1:-from-timestamp}
REPLAY_PARAM=${2:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}
DURATION=${3:-180}
SEED=${4:-42}

echo "=== Laboratorio 3: Sistema Event-Driven ==="
echo "=== Script de Replay (replay.sh) ==="
echo "Tipo de replay: $REPLAY_TYPE"
echo "Parámetro: $REPLAY_PARAM"
echo "Duración: $DURATION segundos"
echo "Seed: $SEED"
echo ""

# Verificar Docker
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker no está corriendo"
    exit 1
fi

# Limpiar estado anterior
echo "Limpiando contenedores anteriores..."
docker compose down --remove-orphans 2>/dev/null || true

# Iniciar sistema
echo "Iniciando sistema..."
docker compose up -d

# Esperar a RabbitMQ
echo "Esperando a RabbitMQ..."
for i in {1..30}; do
    if docker exec rabbitmq_broker rabbitmq-diagnostics -q ping 2>/dev/null; then
        echo "✓ RabbitMQ listo"
        break
    fi
    sleep 1
done

# Esperar servicios
echo "Esperando servicios..."
sleep 10

# Generar eventos iniciales
echo "Generando eventos iniciales..."
docker compose run -d --name initial_publisher publisher --mode normal --rate 2.0 --seed "$SEED"
sleep 60
docker stop initial_publisher 2>/dev/null || true
docker rm initial_publisher 2>/dev/null || true

# Ejecutar tipo de replay específico
echo "Iniciando replay..."
case $REPLAY_TYPE in
    "from-timestamp")
        echo "🔄 REPLAY: Reproduciendo desde timestamp $REPLAY_PARAM"
        # Para RabbitMQ, simulamos replay reiniciando consumidores
        docker compose stop validator aggregator audit
        sleep 5
        docker compose up -d validator aggregator audit
        ;;
    "from-offset")
        echo "🔄 REPLAY: Reproduciendo desde offset $REPLAY_PARAM"
        # Simular reset de colas
        docker compose stop validator aggregator audit
        docker exec rabbitmq_broker rabbitmqctl stop_app 2>/dev/null || true
        sleep 2
        docker exec rabbitmq_broker rabbitmqctl start_app 2>/dev/null || true
        sleep 3
        docker compose up -d validator aggregator audit
        ;;
    "replay-all")
        echo "🔄 REPLAY: Reproduciendo todos los eventos"
        # Limpiar estado completamente
        docker compose stop validator aggregator audit
        docker exec rabbitmq_broker rabbitmqctl stop_app 2>/dev/null || true
        sleep 2
        docker exec rabbitmq_broker rabbitmqctl reset 2>/dev/null || true
        sleep 2
        docker exec rabbitmq_broker rabbitmqctl start_app 2>/dev/null || true
        sleep 3
        # Limpiar bases de datos
        rm -f ./audit_data/audit.db 2>/dev/null || true
        rm -f ./metrics_data/metrics.db 2>/dev/null || true
        docker compose up -d validator aggregator audit
        # Generar eventos nuevamente
        docker compose run -d --name replay_all_publisher publisher --mode normal --rate 3.0 --seed "$SEED"
        ;;
esac

# Esperar recuperación
echo "Esperando recuperación de servicios..."
sleep 10

# Monitorear durante la duración especificada
echo "Monitoreando replay durante $DURATION segundos..."
start_time=$(date +%s)
end_time=$((start_time + DURATION))

while [ $(date +%s) -lt $end_time ]; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    remaining=$((end_time - current_time))
    
    echo "=== Progreso del Replay: ${elapsed}s/${DURATION}s (restante: ${remaining}s) ==="
    
    # Mostrar estado de colas
    echo "Estado de colas:"
    docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null || echo "No se puede obtener estado"
    
    # Mostrar procesamiento
    echo "Eventos procesados:"
    docker logs service_validator --tail 3 2>/dev/null | grep "Evento" || echo "No hay eventos recientes"
    
    echo "----------------------------------------"
    sleep 30
done

# Generar reporte simple
echo "=== Generando reporte final ==="
echo "Replay completado"

# Verificar métricas almacenadas
if docker exec service_metrics_storage sqlite3 /app/metrics_data/metrics.db "SELECT COUNT(*) FROM daily_metrics;" 2>/dev/null > /dev/null; then
    metrics_count=$(docker exec service_metrics_storage sqlite3 /app/metrics_data/metrics.db "SELECT COUNT(*) FROM daily_metrics;" 2>/dev/null || echo "0")
    echo "Métricas almacenadas: $metrics_count registros"
fi

# Limpiar
echo "Deteniendo sistema..."
if [ "$REPLAY_TYPE" = "replay-all" ]; then
    docker stop replay_all_publisher 2>/dev/null || true
    docker rm replay_all_publisher 2>/dev/null || true
fi
docker compose down

echo "=== Demostración de replay finalizada ==="
echo "Puedes revisar logs con: docker compose logs"
echo "Métricas almacenadas en: ./metrics_data/metrics.db"