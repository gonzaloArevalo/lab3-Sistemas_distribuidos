#!/bin/bash

# run_chaos.sh - Script para ejecutar pruebas de caos
# Laboratorio 3: Publish & Subscribe - Sistema Event-Driven

set -e

# Configuración por defecto
CHAOS_TYPE=${1:-mixed}
DURATION=${2:-300}
SEED=${3:-42}

echo "=== Laboratorio 3: Sistema Event-Driven ==="
echo "=== Script de Pruebas de Caos (run_chaos.sh) ==="
echo "Tipo de caos: $CHAOS_TYPE"
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

# Iniciar publisher con carga base
echo "Iniciando publisher con carga base..."
docker compose run -d --name chaos_base_publisher publisher --mode normal --rate 1.0 --seed "$SEED"

# Monitorear y ejecutar caos durante la duración especificada
echo "Iniciando pruebas de caos durante $DURATION segundos..."
start_time=$(date +%s)
end_time=$((start_time + DURATION))
chaos_count=0

while [ $(date +%s) -lt $end_time ]; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    remaining=$((end_time - current_time))
    
    echo "=== Ciclo de Caos #$chaos_count ==="
    echo "Progreso: ${elapsed}s/${DURATION}s (restante: ${remaining}s)"
    
    # Mostrar estado de colas
    echo "Estado de colas:"
    docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null || echo "No se puede obtener estado"
    
    # Ejecutar tipo de caos
    case $CHAOS_TYPE in
        "kill-consumer")
            # Matar un consumidor aleatorio
            consumers=("service_validator" "service_aggregator" "service_audit")
            target=${consumers[$RANDOM % ${#consumers[@]}]}
            echo "CAOS: Matando consumidor $target"
            docker kill "$target" 2>/dev/null || echo "$target no estaba corriendo"
            sleep 5
            echo "RECUPERACIÓN: Reiniciando $target"
            docker compose up -d "${target#service_}"
            ;;
        "restart-broker")
            # Reiniciar el broker
            echo "CAOS: Reiniciando broker RabbitMQ"
            docker compose restart rabbitmq
            echo "Esperando recuperación de RabbitMQ..."
            for i in {1..30}; do
                if docker exec rabbitmq_broker rabbitmq-diagnostics -q ping 2>/dev/null; then
                    echo "✓ RabbitMQ recuperado"
                    break
                fi
                sleep 2
            done
            ;;
        "mixed")
            # Caos mixto aleatorio
            chaos_choice=$((RANDOM % 3))
            case $chaos_choice in
                0)
                    consumers=("service_validator" "service_aggregator" "service_audit")
                    target=${consumers[$RANDOM % ${#consumers[@]}]}
                    echo "CAOS: Matando consumidor $target"
                    docker kill "$target" 2>/dev/null || echo "$target no estaba corriendo"
                    sleep 5
                    echo "RECUPERACIÓN: Reiniciando $target"
                    docker compose up -d "${target#service_}"
                    ;;
                1)
                    echo "CAOS: Reiniciando broker RabbitMQ"
                    docker compose restart rabbitmq
                    for i in {1..30}; do
                        if docker exec rabbitmq_broker rabbitmq-diagnostics -q ping 2>/dev/null; then
                            echo "✓ RabbitMQ recuperado"
                            break
                        fi
                        sleep 2
                    done
                    ;;
                2)
                    echo "CAOS: Inyectando carga adicional"
                    docker compose run -d --name chaos_burst_publisher publisher --mode burst --seed "$SEED"
                    sleep 10
                    docker stop chaos_burst_publisher 2>/dev/null || true
                    docker rm chaos_burst_publisher 2>/dev/null || true
                    ;;
            esac
            ;;
    esac
    
    # Esperar recuperación
    echo "Esperando estabilización..."
    sleep 20
    
    # Mostrar estado post-caos
    echo "Estado post-caos:"
    docker exec rabbitmq_broker rabbitmqctl list_queues name messages 2>/dev/null || echo "No se puede obtener estado"
    
    echo "----------------------------------------"
    chaos_count=$((chaos_count + 1))
done

# Generar reporte simple
echo "=== Generando reporte final ==="
base_events=$(docker logs chaos_base_publisher 2>/dev/null | grep -c "Evento publicado" || echo "0")
echo "Total de eventos publicados: $base_events"

# Verificar estado final de servicios
echo "Estado final de servicios:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(service_|rabbitmq_)" || echo "No hay servicios corriendo"

# Limpiar
echo "Deteniendo sistema..."
docker stop chaos_base_publisher 2>/dev/null || true
docker rm chaos_base_publisher 2>/dev/null || true
docker compose down

echo "=== Prueba de caos finalizada ==="
echo "Puedes revisar logs con: docker compose logs"
echo "Métricas almacenadas en: ./metrics_data/metrics.db"