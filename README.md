# Lab 3 – País X (Event-Driven Architecture)

Sistema event-driven con RabbitMQ para procesamiento de eventos de seguridad, victimización y migración. Implementa el pipeline completo: Publisher → Validator → Aggregator → Audit → Metrics.

## Arquitectura

- **Publisher**: Genera eventos sintéticos (security.incident, survey.victimization, migration.case)
- **Validator**: Valida esquemas JSON y reenvía eventos válidos
- **Aggregator**: Deduplica y agrega por ventanas diarias por región
- **Audit**: Persiste trazabilidad de eventos en SQLite
- **Metrics Storage**: Almacena métricas agregadas para consulta
- **RabbitMQ**: Broker pub-sub con topic exchange y deadletter queues

## Requisitos del Lab Implementados

### Requisitos Funcionales (RF)
- **RF1**: Delivery at-least-once end-to-end ✅
- **RF2**: Idempotencia y deduplicación por event_id ✅
- **RF3**: Backpressure y retries (básico) ⚠️
- **RF4**: Tolerancia a fallas con recuperación automática ✅
- **RF5**: Replay de eventos (script implementado) ⚠️
- **RF6**: Observabilidad con logs estructurados JSON ✅
- **RF7**: Reproducibilidad con seed en publisher ✅
- **RF8**: Runtime ≤ 8 minutos ✅
- **RF9**: Datos sintéticos, neutros ✅

### Requisitos Técnicos (RT)
- **RT1**: 6 contenedores Docker separados ✅
- **RT2**: Docker Compose orquestación ✅
- **RT3**: CI/CD configurado (GitHub Actions) ✅
- **RT4**: Documentación completa ✅
- **RT5**: Schemas JSON para validación ✅
- **RT6**: Scripts de demo ✅
- **RT7**: Tests unitarios y de integración ✅

## Ejecución del Sistema

### Prerrequisitos

- Docker y Docker Compose
- Terminal en el directorio raíz (donde está `docker-compose.yml`)

### 1. Levantar Sistema Completo

```bash
# Levantar todos los servicios
docker compose up --build

# O en segundo plano
docker compose up -d --build
docker compose logs -f  # seguir todos los logs
```

El orden de inicio es: RabbitMQ → Validator → Publisher → Aggregator → Audit → Metrics

### 2. Ejecución Paso a Paso

#### 2.1 Levantar RabbitMQ
```bash
docker compose up -d rabbitmq
```
Esperar a que el healthcheck pase (unos 15 segundos). Opcional: acceder a http://localhost:15672 (usuario/contraseña: `guest`/`guest`)

#### 2.2 Levantar Validator
```bash
docker compose up -d validator
```
El validator crea colas y exchanges necesarios. Verificar logs:
```bash
docker compose logs -f validator
```

#### 2.3 Levantar Aggregator
```bash
docker compose up -d aggregator
```

#### 2.4 Levantar Audit y Metrics
```bash
docker compose up -d audit metrics-storage
```

#### 2.5 Levantar Publisher
```bash
docker compose up -d publisher
```

### 3. Scripts de Demostración

#### 3.1 Carga Normal
```bash
./scripts/run_load.sh [tasa] [duración_segundos] [seed]
# Ejemplo:
./scripts/run_load.sh 2.0 300 42
```

#### 3.2 Carga con Picos (Burst)
```bash
./scripts/run_burst.sh [pico_eventos] [tasa_normal] [seed]
# Ejemplo:
./scripts/run_burst.sh 100 1.0 42
```

#### 3.3 Pruebas de Caos
```bash
./scripts/run_chaos.sh
# Mata servicios aleatoriamente para probar recuperación
```

#### 3.4 Replay de Eventos
```bash
./scripts/replay.sh [fecha_inicio] [fecha_fin]
# Ejemplo:
./scripts/replay.sh 2025-01-15 2025-01-16
```

### 4. Modos del Publisher

```bash
# Modo normal (default)
docker compose run --rm publisher -- --mode normal --rate 1.0 --seed 42

# Modo burst (picos de eventos)
docker compose run --rm publisher -- --mode burst --burst_count 50 --rate 2.0

# Modo duplicados (para probar deduplicación)
docker compose run --rm publisher -- --mode duplicates --dup_rate 0.1

# Modo out-of-order (timestamps fuera de orden)
docker compose run --rm publisher -- --mode out_of_order --disorder_rate 0.2
```

### 5. Tests

```bash
# Ejecutar todos los tests
python3 -m venv test_env
source test_env/bin/activate
pip install -r tests/requirements.txt
python -m pytest tests/ -v

# Tests específicos de requisitos del lab
python -m pytest tests/test_lab_requirements.py -v

# Tests de integración con RabbitMQ
python -m pytest tests/test_rabbitmq_integration.py -v
```

### 5.1 CI/CD

El proyecto incluye configuración de CI/CD con GitHub Actions en `.github/workflows/ci.yml`:

**Validaciones automáticas:**
- Sintaxis de Docker Compose
- Validación de schemas JSON
- Verificación de archivos requeridos
- Sintaxis de Python en todos los servicios
- Permisos de scripts ejecutables
- Estructura de Dockerfiles
- Build de imágenes Docker (en main)

**Ejecución:**
- **Pull Requests**: Validación básica
- **Push a main**: Validación + build completo

**Estado del CI:** ✅ Configurado y funcional

### 6. Monitoreo y Observabilidad

#### 6.1 Logs Estructurados
Todos los servicios generan logs en formato JSON:
```bash
# Ver logs de un servicio específico
docker compose logs -f validator
docker compose logs -f aggregator
docker compose logs -f publisher
```

#### 6.2 RabbitMQ Management UI
- URL: http://localhost:15672
- Usuario: `guest` / Contraseña: `guest`

Métricas disponibles:
- **Queues**: `validator_queue`, `aggregator_queue`, `deadletter.validation`, `deadletter.processing`
- **Exchanges**: `events_topic` (topic exchange)
- **Rates**: mensajes/segundo por cola
- **Lag**: mensajes pendientes de procesamiento

#### 6.3 Consultar Métricas Almacenadas
```bash
# Conectarse al contenedor de metrics
docker compose exec metrics-storage sqlite3 /app/metrics_data/metrics.db

# Consultar métricas diarias
SELECT date, region, event_type, count, metrics_json FROM daily_metrics ORDER BY date DESC, region;

# Consultar trazabilidad
docker compose exec audit sqlite3 /app/audit_data/audit.db
SELECT event_id, input_timestamp, metric_id, contribution_type FROM event_tracing WHERE event_id = 'uuid';
```

### 7. Demo Completa (8 minutos)

```bash
# 1. Ingestión (1.5 min)
./scripts/run_load.sh 2.0 90 42

# 2. Validación (1 min) - observar logs del validator
docker compose logs -f validator | head -20

# 3. Métricas (1.5 min) - consultar métricas generadas
docker compose exec metrics-storage sqlite3 /app/metrics_data/metrics.db "SELECT * FROM daily_metrics LIMIT 5;"

# 4. Falla inducida (1.5 min)
docker compose stop validator
sleep 30
docker compose start validator

# 5. Recuperación (1 min) - verificar reanudación del procesamiento
docker compose logs -f validator | tail -10

# 6. Replay (1.5 min)
./scripts/replay.sh 2025-01-15 2025-01-16
```

### 8. Parar Sistema

```bash
# Parar todos los servicios
docker compose down

# Limpiar volúmenes (datos)
docker compose down -v

# Reconstruir imágenes
docker compose build --no-cache
```

## Estructura del Proyecto

```
├── docker-compose.yml          # Orquestación de servicios
├── .github/workflows/          # CI/CD con GitHub Actions
│   └── ci.yml                 # Pipeline de validación y build
├── schemas/                    # JSON schemas para validación
│   ├── event_schema.json
│   ├── payload_security_incident.json
│   ├── payload_survey_victimization.json
│   └── payload_migration_case.json
├── scripts/                    # Scripts de demostración
│   ├── run_load.sh
│   ├── run_burst.sh
│   ├── run_chaos.sh
│   └── replay.sh
├── servicios/                  # Código fuente de microservicios
│   ├── publisher/
│   ├── validator/
│   ├── aggregator/
│   ├── audit/
│   └── metrics api/
├── tests/                      # Tests unitarios y de integración
├── audit_data/                 # Datos persistentes de audit (SQLite)
└── metrics_data/               # Datos persistentes de métricas (SQLite)
```

## Configuración de Servicios

### Publisher
- **Modos**: normal, burst, duplicates, out_of_order
- **Tasa configurable**: eventos por segundo
- **Seed**: para reproducibilidad
- **Regiones**: norte, sur, centro, este, oeste

### Validator
- **Validación**: esquema JSON completo
- **Deadletter**: `deadletter.validation` para eventos inválidos
- **Reenvío**: eventos válidos a aggregator_queue

### Aggregator
- **Deduplicación**: por event_id (TTL 2 días)
- **Ventanas**: diarias por región (UTC)
- **Flush**: cada 60 segundos
- **Deadletter**: `deadletter.processing` para errores

### Audit
- **Almacenamiento**: SQLite
- **Trazabilidad**: eventos de entrada → métricas de salida
- **Tablas**: input_events, output_metrics, event_tracing

### Metrics Storage
- **Almacenamiento**: SQLite
- **Consulta**: directa vía SQLite CLI
- **Formato**: métricas en JSON

## Limitaciones Conocidas

1. **API REST**: Metrics solo almacena, no expone HTTP
2. **Backpressure**: Implementación básica
3. **Consumer Groups**: No se utiliza paralelismo real
4. **Replay**: Script implementado pero funcionalidad limitada

## Métricas de Observabilidad

Los servicios exponen las siguientes métricas en logs:
- **throughput**: eventos procesados por segundo
- **error_rate**: errores por segundo  
- **lag/backlog**: eventos pendientes en colas
- **validated_count**: eventos válidos procesados
- **deduplicated_count**: eventos duplicados descartados
- **metrics_published**: métricas generadas

## Troubleshooting

### Problemas Comunes

1. **RabbitMQ no está listo**
   ```bash
   docker compose logs rabbitmq
   # Esperar a que "Server startup complete" aparezca
   ```

2. **Colas no se crean**
   ```bash
   # Reiniciar validator para crear infraestructura
   docker compose restart validator
   ```

3. **Eventos se acumulan (backlog)**
   ```bash
   # Ver estado de colas en RabbitMQ UI
   # O escalar aggregator (no soportado en esta versión)
   ```

4. **Base de datos corrupta**
   ```bash
   docker compose down -v
   docker compose up --build
   ```

### Logs Útiles

```bash
# Todos los servicios en tiempo real
docker compose logs -f

# Servicio específico
docker compose logs -f validator

# Últimos 50 errores
docker compose logs --tail=50 | grep ERROR
```
