#!/bin/bash

# run_load.sh - Script para ejecutar carga normal de eventos
# Laboratorio 3: Publish & Subscribe - Sistema Event-Driven

set -e

# Configuración por defecto
RATE=${1:-2.0}
DURATION=${2:-300}
SEED=${3:-42}

echo "=== Laboratorio 3: Sistema Event-Driven ==="
echo "=== Script de Carga Normal (run_load.sh) ==="
echo "Tasa: $RATE eventos/segundo"
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

# Iniciar publisher con configuración específica
echo "Iniciando publisher con carga normal..."
docker compose run -d --name load_publisher publisher --mode normal --rate "$RATE" --seed "$SEED"

# Monitorear durante la duración especificada
echo "Monitoreando durante $DURATION segundos..."
start_time=$(date +%s)
end_time=$((start_time + DURATION))

while [ $(date +%s) -lt $end_time ]; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    remaining=$((end_time - current_time))
    
    echo "=== Progreso: ${elapsed}s/${DURATION}s (restante: ${remaining}s) ==="
    
    # Mostrar estado de colas
    echo "Estado de colas:"
    docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null || echo "No se puede obtener estado"
    
    # Mostrar logs recientes del publisher
    echo "Eventos publicados recientes:"
    docker logs load_publisher --tail 5 2>/dev/null | grep "Evento" || echo "No hay eventos recientes"
    
    echo "----------------------------------------"
    sleep 30
done

# Generar reporte simple
echo "=== Generando reporte final ==="
total_events=$(docker logs load_publisher 2>/dev/null | grep -c "Evento" || echo "0")
echo "Total de eventos publicados: $total_events"

# Limpiar
echo "Deteniendo sistema..."
docker stop load_publisher 2>/dev/null || true
docker rm load_publisher 2>/dev/null || true
docker compose down

echo "=== Prueba de carga finalizada ==="
echo "Puedes revisar logs con: docker compose logs"
echo "Métricas almacenadas en: ./metrics_data/metrics.db"