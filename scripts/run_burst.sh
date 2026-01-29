#!/bin/bash

# run_burst.sh - Script para ejecutar carga con picos (burst)
# Laboratorio 3: Publish & Subscribe - Sistema Event-Driven

set -e

# Configuración por defecto
BURST_COUNT=${1:-50}
BURST_INTERVAL=${2:-10}
DURATION=${3:-300}
SEED=${4:-42}

echo "=== Laboratorio 3: Sistema Event-Driven ==="
echo "=== Script de Carga con Picos (run_burst.sh) ==="
echo "Eventos por ráfaga: $BURST_COUNT"
echo "Intervalo entre ráfagas: $BURST_INTERVAL segundos"
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

# Iniciar publisher en modo burst
echo "Iniciando publisher en modo burst..."
docker compose run -d --name burst_publisher publisher --mode burst --seed "$SEED"

# Monitorear durante la duración especificada
echo "Monitoreando durante $DURATION segundos..."
start_time=$(date +%s)
end_time=$((start_time + DURATION))
burst_cycle=0

while [ $(date +%s) -lt $end_time ]; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    remaining=$((end_time - current_time))
    
    echo "=== Ciclo de Burst #$burst_cycle ==="
    echo "Progreso: ${elapsed}s/${DURATION}s (restante: ${remaining}s)"
    
    # Mostrar estado de colas
    echo "Estado de colas:"
    docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null || echo "No se puede obtener estado"
    
    # Mostrar logs recientes del publisher
    echo "Eventos de ráfaga publicados:"
    docker logs burst_publisher --tail 5 2>/dev/null | grep "Evento" || echo "No hay eventos recientes"
    
    # Detectar backpressure simple
    queue_size=$(docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null | awk 'NR>1 {sum+=$2} END {print sum+0}')
    if [ "$queue_size" -gt 100 ]; then
        echo "⚠ Backpressure detectado: $queue_size mensajes en colas"
    fi
    
    echo "----------------------------------------"
    sleep $BURST_INTERVAL
    burst_cycle=$((burst_cycle + 1))
done

# Generar reporte simple
echo "=== Generando reporte final ==="
total_events=$(docker logs burst_publisher 2>/dev/null | grep -c "Evento" || echo "0")
burst_events=$(docker logs burst_publisher 2>/dev/null | grep -c "ráfaga" || echo "0")
echo "Total de eventos publicados: $total_events"
echo "Eventos de ráfaga: $burst_events"

# Limpiar
echo "Deteniendo sistema..."
docker stop burst_publisher 2>/dev/null || true
docker rm burst_publisher 2>/dev/null || true
docker compose down

echo "=== Prueba de burst finalizada ==="
echo "Puedes revisar logs con: docker compose logs"
echo "Métricas almacenadas en: ./metrics_data/metrics.db"