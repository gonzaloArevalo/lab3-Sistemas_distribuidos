#!/bin/bash

# Función para imprimir cabeceras bonitas
function print_header {
    echo "=========================================="
    echo "      SISTEMA DE REPLAY DE EVENTOS"
    echo "=========================================="
}

print_header

# 1. Verificamos si el sistema base (Audit) está corriendo
if [ -z "$(docker compose ps -q audit)" ]; then
    echo "ERROR: El contenedor 'audit' no está corriendo."
    echo "   Por favor inicia el sistema primero (ej: ./run_load.sh o docker compose up -d)"
    exit 1
fi

# 2. Preguntar si se desea detener el tráfico vivo (Publisher)
echo "¿Deseas detener el Publisher (tráfico vivo) para ver mejor el replay?"
read -p "Escribe 's' para detener o 'n' para continuar con tráfico mixto [s/N]: " stop_pub

if [[ "$stop_pub" =~ ^[sS]$ ]]; then
    echo "Deteniendo Publisher..."
    docker compose stop publisher
    echo "Publisher detenido. El sistema está en silencio."
else
    echo "Continuando con Publisher encendido (Tráfico Mixto)."
fi

echo ""
echo "Selecciona el modo de Replay:"
echo "   1) Replay COMPLETO (Todo el historial)"
echo "   2) Replay por OFFSET (Saltar N primeros eventos)"
echo "   3) Replay por TIEMPO (Desde una fecha específica)"
echo "   4) Cancelar"
echo ""
read -p "Opción [1-4]: " option

case $option in
    1)
        echo "Iniciando Replay Completo..."
        docker compose exec audit python replay.py
        ;;
    2)
        read -p "Introduce el número de línea (Offset) desde donde empezar [ej: 50]: " offset_num
        # Verificamos que sea un número
        if ! [[ "$offset_num" =~ ^[0-9]+$ ]]; then
            echo "Error: Debes ingresar un número válido."
            exit 1
        fi
        echo "Iniciando Replay desde offset $offset_num..."
        docker compose exec audit python replay.py --offset "$offset_num"
        ;;
    3)
        echo "Formato requerido: YYYY-MM-DDTHH:MM:SS"
        echo "Ejemplo: $(date +%Y-%m-%dT%H:%M:%S)"
        read -p "Introduce la fecha de inicio ISO: " timestamp_str
        
        if [ -z "$timestamp_str" ]; then
             echo "Error: La fecha no puede estar vacía."
             exit 1
        fi
        echo "Iniciando Replay desde $timestamp_str..."
        # Nota: Las comillas alrededor de la variable son importantes
        docker compose exec audit python replay.py --timestamp "$timestamp_str"
        ;;
    4)
        echo "Operación cancelada."
        exit 0
        ;;
    *)
        echo "Opción no válida."
        exit 1
        ;;
esac

echo ""
echo "✅ Script finalizado."