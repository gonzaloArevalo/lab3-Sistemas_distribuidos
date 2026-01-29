# Laboratorio 3: Publish & Subscribe

### Sistema Event-Driven para Ingesta y Agregaci ́on de Eventos

### Departamento de Ingenier ́a Inform ́aticaı

### Universidad de Santiago de Chile

### Prof. Miguel C ́arcamo

### Semestre 2-

## 1. Objetivos Pedag ́ogicos

```
Al nalizar este laboratorio, los estudiantes ser ́an capaces de:
Dise ̃nar e implementar sistemas event-driven usando patrones publish-subscribe
Comprender y aplicar sem ́anticas de entrega (at-least-once) en sistemas distribuidos
Implementar mecanismos de idempotencia y deduplicaci ́on de eventos
Manejar eventos duplicados y fuera de orden (out-of-order) en pipelines de proce-
samiento
Dise ̃nar estrategias de backpressure y retries con pol ́ticas deı nidas
Implementar tolerancia a fallas en sistemas pub-sub (recuperaci ́on de consumidores
y brokers)
Demostrar capacidades de replay y re-procesamiento seg ́un la tecnolog ́a elegidaı
Implementar observabilidad m ́nima: logs estructurados y m ́etricas (throughput,ı
error rate, lag/backlog)
Comparar diferentes tecnolog ́as pub-sub (Kafka, RabbitMQ, MQTT, NATS JetS-ı
tream, Redis Streams) resolviendo el mismo problema
Aplicar buenas pr ́acticas de DevOps: contenedores, CI/CD, y reproducibilidad
```
## 2. Contexto del Curso y Log ́sticaı

### 2.1. Organizaci ́on

```
N ́umero de estudiantes: 20 estudiantes
Formaci ́on de grupos: 5 grupos de 4 integrantes
Duraci ́on del laboratorio: Aproximadamente 1 mes (4 semanas)
Modalidad: Cada grupo implementa el mismo problema usando una tecnolog ́aı
diferente
```

### 2.2. Elecci ́on de Tecnolog ́ası

```
Cada grupo debe elegir una de las siguientes tecnolog ́as pub-sub:ı
```
1. Kafka o Redpanda (Kafka-compatible)
2. RabbitMQ
3. MQTT (Mosquitto)
4. NATS JetStream
5. Redis Streams
    Importante:
       Cada grupo debe comunicar su elecci ́on de tecnolog ́a al profesor lo antes posible aı
       trav ́es de Google Classroom.
       Se recomienda que los grupos no repitan tecnolog ́as para permitir comparaci ́onı
       entre diferentes soluciones.
       Todas las tecnolog ́as deben resolver el mismo problema y cumplir los mismos re-ı
       quisitos funcionales para permitir comparaci ́on entre grupos.

### 2.3. Lenguaje de Programaci ́on

```
Sugerido: Python (por simplicidad y ecosistema)
Alternativas permitidas: Go, Java (si el grupo lo preere)
Requisito: El lenguaje debe tener clientes maduros para la tecnolog ́a pub-subı
elegida
```
### 2.4. Entrega

```
Plataforma: Repositorio Git (GitLab o GitHub)
Requisito: CI/CD congurado (al menos compilaci ́on/validaci ́on b ́asica)
Formato: Repositorio p ́ublico o privado con acceso para el profesor
```
## 3. Descripci ́on del Problema

### 3.1. Contexto del Sistema

Se requiere desarrollar un sistema event-driven para el procesamiento de eventos
de un pa ́sı cticio (denominado Pa ́s Xı ). El sistema debe manejar datos sint ́eticos y
neutrales, sin referencias a pa ́ses o situaciones reales.ı
Prop ́osito del sistema: El sistema est ́a dise ̃nado para dar cuenta del estado de de-
lincuencia y seguridad de diferentes zonas o regiones de un pa ́s. A trav ́es de la recolecci ́on,ı
procesamiento y agregaci ́on de informaci ́on sobre delincuencia, victimizaci ́on y migraci ́on,


el sistema permite generar m ́etricas y an ́alisis que contribuyen a la comprensi ́on de los
patrones de seguridad en diferentes ́areas geogr ́acas.
El sistema generar ́a y procesar ́a tres tipos de eventos de forma aleatoria y continua-
mente:
Delitos (security.incident): Eventos relacionados con actos delictuales reporta-
dos en diferentes regiones
Encuestas de victimizaci ́on (survey.victimization): Respuestas de encuestas
sobre experiencias de victimizaci ́on de la poblaci ́on
Casos de migraci ́on (migration.case): Casos relacionados con procesos migra-
torios que pueden estar asociados a factores de seguridad
Estos eventos, una vez procesados y agregados, permiten generar m ́etricas diarias por
regi ́on que reejan el estado de seguridad y delincuencia de cada zona, facilitando la toma
de decisiones y el an ́alisis de tendencias.

### 3.2. Flujo del Sistema

```
El sistema debe implementar el siguiente pipeline:
```
1. Generaci ́on/Publicaci ́on: Un generador crea eventos sint ́eticos y los publica en
    los t ́opicos correspondientes
2. Validaci ́on: Un validador consume eventos, valida su esquema, y env ́a eventosı
    inv ́alidos a una cola de deadletter
3. Agregaci ́on: Un agregador consume eventos v ́alidos, los deduplica, agrega por ven-
    tanas diarias por regi ́on, y publica m ́etricas
4. Auditor ́a:ı Un servicio de auditor ́a que persiste la trazabilidad de eventos (qu ́eı
    eventos de entrada contribuyeron a qu ́e m ́etricas de salida)
5. Visualizaci ́on: Una API o dashboard m ́nimo permite consultar m ́etricas agregadası

### 3.3. Arquitectura M ́nimaı

El sistema debe implementarse siguiendo una arquitectura de microservicios, donde
cada servicio principal debe ejecutarse en un contenedor Docker separado. Esta separaci ́on
permite:

```
Distribuci ́on real: Demostrar que el sistema es verdaderamente distribuido
Tolerancia a fallas: Poder matar servicios individuales para probar recuperaci ́on
Escalabilidad: Escalar servicios independientemente seg ́un necesidad
Aislamiento: Cada servicio puede fallar sin afectar a los dem ́as
Requisitos de contenedores:
```

```
Servicios obligatorios separados: Los siguientes servicios deben estar en conte-
nedores distintos:
```
1. Publisher/Generator
2. Validator
3. Aggregator
4. Audit/Trazabilidad
5. Metrics API/Dashboard
Broker pub-sub: Debe estar en su propio contenedor (Kafka, RabbitMQ, Mos-
quitto, NATS, Redis seg ́un tecnolog ́a elegida)ı
Base de datos: Si se usa PostgreSQL, debe estar en contenedor separado. SQLite
puede estar en el mismo contenedor que Audit/Trazabilidad
Orquestaci ́on: Todos los servicios deben levantarse con docker compose up
Comunicaci ́on: Los servicios deben comunicarse a trav ́es de la red de Docker
(usando nombres de servicio de docker-compose)
Nota: Si un grupo necesita combinar algunos servicios menores por razones t ́ecnicas
v ́alidas, debe justicarlo en el README. Sin embargo, los 5 servicios principales deben
estar separados.
La arquitectura m ́nima del sistema es:ı


```
Sistema Event-Driven (Pa ́ıs X - Sint ́etico)
```
```
Publisher/
Generator
```
```
security.incident victimizationsurvey. migration.case
```
```
Broker
Pub-Sub
```
```
deadletter.validation Validator
```
```
deadletter.processing Aggregator metrics.daily
```
```
Audit/
Trazabilidad
```
```
Metrics
API/
Dashboard
```
```
anomalyalerts.
(BONUS)
```
```
consume
invalidos
```
```
validos
errores m ́etricas
```
Leyenda:
Servicios (microservicios en contenedores)
T ́opicos/Streams del broker
Deadletter queues
Broker pub-sub
Funcionalidad bonus


## 4. Especicaci ́on de T ́opicos

### 4.1. T ́opicos Obligatorios

```
El sistema debe implementar los siguientes t ́opicos:
```
1. security.incident - Eventos de delitos reportados
2. survey.victimization - Eventos de encuestas de victimizaci ́on
3. migration.case - Eventos de casos de migraci ́on
4. metrics.daily - M ́etricas agregadas diarias por regi ́on
5. deadletter.validation - Eventos que fallaron validaci ́on de esquema
6. deadletter.processing - Eventos que fallaron durante el procesamiento
7. alerts.anomaly - (BONUS) Alertas de anomal ́as detectadası

### 4.2. Formato de Eventos

```
Todos los eventos deben seguir el siguiente esquema JSON m ́nimo:ı
{
"event_id":"550e8400-e29b-41d4-a716-446655440000",
"timestamp": "2025-01-15T10:30:00Z",
"region": "norte",
"source": "security.incident",
"schema_version": "1.0",
"correlation_id": "corr-12345",
"payload": {
// Contenido espec ́ıfico del tipo de evento
}
}
```
4.2.1. Campos Obligatorios
eventid: UUID v4 ́unico para cada evento
timestamp: ISO-8601 con timezone (UTC)
region: String identicando la regi ́on (ej:norte, sur,centro,este,oeste)
source: Tipo de evento (debe coincidir con el t ́opico)
schemaversion: Versi ́on del esquema (string semver, ej: 1.0)
correlationid: ID para correlacionar eventos relacionados (opcional pero reco-
mendado)
payload: Objeto JSON con los datos espec ́ıcos del evento


4.2.2. Ejemplos de Payloads
security.incident (delitos):
{
"event_id":"550e8400-e29b-41d4-a716-446655440000",
"timestamp": "2025-01-15T10:30:00Z",
"region": "norte",
"source": "security.incident",
"schema_version": "1.0",
"correlation_id": "corr-12345",
"payload": {
"crime_type":"theft",
"severity": "medium",
"location": {
"latitude":-33.4489,
"longitude": -70.
},
"reported_by": "citizen"
}
}
survey.victimization:
{
"event_id":"660e8400-e29b-41d4-a716-446655440001",
"timestamp": "2025-01-15T11:00:00Z",
"region": "sur",
"source": "survey.victimization",
"schema_version": "1.0",
"correlation_id": "corr-12346",
"payload": {
"survey_id":"survey-2025-001",
"respondent_age": 35 ,
"victimization_type": "property_crime",
"incident_date":"2025-01-10",
"reported": true
}
}
migration.case:
{
"event_id":"770e8400-e29b-41d4-a716-446655440002",
"timestamp": "2025-01-15T11:30:00Z",
"region": "centro",
"source": "migration.case",


```
"schema_version": "1.0",
"correlation_id": "corr-12347",
"payload": {
"case_id": "mig-2025-001",
"case_type":"asylum",
"status":"pending",
"origin_country":"country-x",
"application_date":"2025-01-01"
}
}
```
## 5. Servicios M ́nimos Requeridosı

### 5.1. 1. Publisher/Generator

```
Funci ́on: Genera eventos sint ́eticos y los publica en los t ́opicos correspondientes
Modos de operaci ́on:
```
- Normal: Genera eventos a tasa constante congurable
- Burst: Genera picos de eventos ( ́util para pruebas de backpressure, es decir,
    cuando el sistema debe regular el ujo porque los consumidores no pueden
    procesar eventos tan r ́apido como se publican)
- Duplicados controlados: Inyecta eventos duplicados (mismo eventid) para
    probar deduplicaci ́on
- Out-of-order: Publica eventos con timestamps fuera de orden para probar
    ordenamiento
Reproducibilidad: Debe soportar un par ́ametro --seed para generar eventos re-
producibles
Conguraci ́on: Tasa de eventos, distribuci ́on de regiones, tipos de eventos

### 5.2. 2. Validator

```
Funci ́on: Consume eventos de los t ́opicos de entrada, valida el esquema JSON, y
publica eventos v ́alidos o los env ́a a deadletterı
Validaci ́on:
```
- Vericar presencia de campos obligatorios
- Validar formato de UUID en eventid
- Validar formato ISO-8601 en timestamp
- Validar que source coincida con el t ́opico
- Validar estructura del payload seg ́un el tipo de evento


```
Deadletter: Eventos inv ́alidos deben publicarse en deadletter.validation con
informaci ́on del error
Idempotencia: Debe manejar eventos duplicados correctamente
```
### 5.3. 3. Aggregator

```
Funci ́on: Consume eventos v ́alidos, los deduplica por eventid, agrega por venta-
nas diarias por regi ́on, y publica m ́etricas
Deduplicaci ́on: Mantener un registro de eventid procesados (ventana deslizante
o TTL)
Agregaci ́on:
```
- Ventanas diarias por regi ́on (UTC)
- Contar eventos por tipo y regi ́on
- Calcular m ́etricas b ́asicas (promedios, totales)
Publicaci ́on: Publica m ́etricas agregadas en metrics.daily al nalizar cada d ́aı
Manejo de errores: Eventos que fallan durante el procesamiento van a deadletter.processing

### 5.4. 4. Audit/Trazabilidad

```
Funci ́on: Persiste la trazabilidad de eventos (qu ́e eventos de entrada contribuyeron
a qu ́e m ́etricas de salida)
Almacenamiento: SQLite (desarrollo) o PostgreSQL (producci ́on)
Esquema m ́nimo:ı
```
- Tabla de eventos de entrada (eventid, timestamp, region, source, payload)
- Tabla de m ́etricas de salida (metricid, date, region, metrics)
- Tabla de trazabilidad (eventid, metricid, contributiontype)
Consultas: Debe permitir consultar qu ́e eventos contribuyeron a una m ́etrica es-
pec ́ıca

### 5.5. 5. Metrics API / Dashboard

```
Funci ́on: Expone m ́etricas agregadas para consulta
Implementaci ́on m ́nima:ı
```
- Endpoint REST /metrics que retorna m ́etricas en JSON
- Filtros por regi ́on, fecha, tipo de evento
- Alternativa: Exportar a archivo o base de datos consultable
Formato de respuesta:


```
{
"date":"2025-01-15",
"region": "norte",
"metrics": {
"security.incident": {
"count": 150 ,
"by_severity": {
"low": 50 ,
"medium": 80 ,
"high": 20
},
"by_crime_type": {
"theft": 60 ,
"assault": 40 ,
"burglary": 30 ,
"other": 20
}
},
"survey.victimization": {
"count": 200 ,
"reported_rate": 0.
},
"migration.case": {
"count": 75 ,
"by_status": {
"pending": 30 ,
"approved": 25 ,
"rejected": 20
}
}
}
}
```
## 6. Requisitos No Negociables

```
Los siguientes requisitos son obligatorios y deben demostrarse durante la evaluaci ́on:
```
### 6.1. Checklist de Requisitos Funcionales

RF1: Delivery at-least-once end-to-end: El sistema debe garantizar que cada evento
v ́alido se procese al menos una vez, desde la publicaci ́on hasta la m ́etrica nal
RF2: Idempotencia y deduplicaci ́on: El agregador debe detectar y eliminar eventos
duplicados (mismo eventid) antes de agregar
RF3: Backpressure y retries: El sistema debe implementar:


```
Pol ́tica de retry conı gurable: Cuando un evento falla al ser procesado
(por ejemplo, error de validaci ́on o fallo temporal del consumidor), el sistema
debe reintentar su procesamiento. La pol ́tica debe ser conı gurable y puede
incluir:
```
- Estrategia de backo: Dene c ́omo aumenta el tiempo de espera entre
    reintentos:
       ◦ Exponencial: El tiempo de espera se duplica en cada intento (ej: 1s,
          2s, 4s, 8s, 16s).Util cuando el problema puede resolverse con tiempo ́
          y se quiere evitar sobrecargar el sistema.
       ◦ Lineal: El tiempo de espera aumenta de forma constante (ej: 1s, 2s,
          3s, 4s, 5s). Balance entre rapidez y carga del sistema.
       ◦ Fijo: El tiempo de espera es constante entre todos los reintentos (ej: 2s,
          2s, 2s, 2s). M ́as simple pero puede sobrecargar si el problema persiste.
- N ́umero m ́aximo de reintentos: L ́mite de intentos antes de enviar elı
    evento a deadletter
- Intervalo inicial: Tiempo base de espera antes del primer reintento
Manejo de backpressure: Cuando los consumidores no pueden procesar
eventos tan r ́apido como se publican, el sistema debe detectar esta situaci ́on y
aplicar mecanismos de regulaci ́on:
- Detectar acumulaci ́on de eventos en el broker (lag/backlog)
- Reducir la tasa de publicaci ́on autom ́aticamente o pausar temporalmente
- Escalar consumidores si es posible (seg ́un la tecnolog ́a)ı
- Monitorear y alertar sobre situaciones de backpressure
L ́mites de reintentos:ı Despu ́es de alcanzar el n ́umero m ́aximo de reintentos
congurado, los eventos que siguen fallando deben ser enviados a deadletter.processing
con informaci ́on del error y n ́umero de intentos realizados
RF4: Tolerancia a fallas: Durante la demo, deben:
Matar un consumidor (validator o aggregator) y mostrar recuperaci ́on au-
tom ́atica
Reiniciar el broker y mostrar que el sistema contin ́ua procesando eventos
Demostrar que no se pierden eventos durante las fallas
RF5: Replay: Deben demostrar capacidad de re-procesamiento:
Reprocesar eventos desde un punto en el tiempo espec ́ıco
Reprocesar eventos desde un oset/posici ́on espec ́ıca
La implementaci ́on depende de la tecnolog ́a (Kafka: oı sets, RabbitMQ: re-
queue, etc.)
RF6: Observabilidad m ́nima:ı
Logs estructurados (JSON) con niveles apropiados
M ́etricas expuestas: throughput (eventos/segundo), error rate (errores/segundo),
lag/backlog (eventos pendientes)


Las m ́etricas pueden exportarse a archivo, base de datos, o endpoint HTTP
RF7: Reproducibilidad:
docker compose up debe levantar todo el sistema
Script make demo (o equivalente) debe ejecutar una demostraci ́on completa
El generador debe soportar --seed para reproducibilidad
RF8: Runtime de demo: La demostraci ́on completa debe ejecutarse en ≤ 8 minutos en
una m ́aquina est ́andar
RF9: Datos sint ́eticos: No usar datos reales ni sensibles; solo datos sint ́eticos generados

### 6.2. Requisitos T ́ecnicos

```
RT1: Contenedores: Los siguientes servicios deben estar en contenedores Docker sepa-
rados:
Publisher/Generator (1 contenedor)
Validator (1 contenedor)
Aggregator (1 contenedor)
Audit/Trazabilidad (1 contenedor, puede incluir SQLite si se usa)
Metrics API/Dashboard (1 contenedor)
Broker pub-sub (1 contenedor: Kafka, RabbitMQ, Mosquitto, NATS, o Redis
seg ́un tecnolog ́a)ı
Base de datos PostgreSQL (1 contenedor, solo si se usa PostgreSQL en lugar
de SQLite)
Total m ́nimo:ı 6 contenedores (5 servicios + 1 broker). Si se usa PostgreSQL: 7
contenedores.
RT2: Orquestaci ́on: Usar docker-compose.yml para orquestar todos los servicios. Los
servicios deben comunicarse usando los nombres de servicio denidos en docker-
compose (ej: validator, aggregator, etc.)
RT3: CI/CD: Repositorio debe tener CI congurado (al menos validaci ́on b ́asica: lint,
compilaci ́on si aplica)
RT4: Documentaci ́on: README.md ejecutable con:
Instrucciones de instalaci ́on y ejecuci ́on
Descripci ́on de cada servicio
C ́omo ejecutar la demo
C ́omo ejecutar tests
RT5: Schemas: Denir esquemas JSON Schema o Avro para validaci ́on (seg ́un tecno-
log ́a)ı
RT6: Scripts:
```

runload.sh - Ejecuta carga normal de eventos
runburst.sh - Ejecuta carga con picos
runchaos.sh - Ejecuta pruebas de caos (matar servicios, reiniciar broker)
replay.sh - Demuestra capacidad de replay
RT7: Tests b ́asicos: Incluir tests unitarios o de integraci ́on b ́asicos (seg ́un el lenguaje)

## 7. Cronograma

```
El laboratorio tiene una duraci ́on aproximada de 4 semanas. A continuaci ́on se presenta
un cronograma sugerido con hitos principales:
```
### 7.1. Semana 1: Dise ̃no y Elecci ́on de Tecnolog ́aı

```
Hitos de la Semana 1:
D ́as 1–3:ı Elecci ́on de tecnolog ́a y dise ̃no de arquitecturaı
```
- Investigar y elegir tecnolog ́a pub-sub (comunicar elecci ́on al profesor)ı
- Revisar documentaci ́on de la tecnolog ́a elegidaı
- Dise ̃nar esquemas de eventos (JSON Schema)
- Denir estructura de contenedores y docker-compose
- Asignar servicios a integrantes del grupo
D ́as 4–5:ı Conguraci ́on inicial y prototipo
- Congurar entorno de desarrollo (Docker, dependencias)
- Crear estructura base del proyecto
- Implementar prototipo b ́asico del Publisher/Generator
- Congurar docker-compose inicial

### 7.2. Semana 2: Implementaci ́on de Servicios Base

```
Hitos de la Semana 2:
D ́as 6–8:ı Implementaci ́on de servicios principales
```
- Implementar Publisher/Generator completo con modo normal
- Implementar Validator con validaci ́on de esquemas
- Implementar Aggregator con deduplicaci ́on b ́asica
- Integrar servicios en docker-compose
D ́as 9–10:ı Integraci ́on y pruebas iniciales
- Integrar todos los servicios
- Probar ujo end-to-end b ́asico
- Identicar y corregir problemas de integraci ́on
- Implementar tests b ́asicos


### 7.3. Semana 3: Robustez y Funcionalidades Avanzadas

```
Hitos de la Semana 3:
D ́as 11–13:ı Implementaci ́on de requisitos avanzados
```
- Implementar backpressure y retries con pol ́tica deı nida
- Implementar tolerancia a fallas (recuperaci ́on de consumidores)
- Implementar replay seg ́un tecnolog ́a elegidaı
- Agregar observabilidad (logs estructurados, m ́etricas)
D ́as 14–15:ı Modos especiales y casos edge
- Implementar modo burst del generador
- Implementar inyecci ́on controlada de duplicados
- Implementar inyecci ́on de eventos out-of-order
- Implementar soporte de seed para reproducibilidad
- Probar tolerancia a fallas del broker

### 7.4. Semana 4: Auditor ́a, Visualizaci ́on y Entregaı

```
Hitos de la Semana 4:
D ́as 16–18:ı Servicios complementarios y scripts
```
- Implementar servicio de Audit/Trazabilidad
- Implementar Metrics API o Dashboard
- Crear scripts de demo (runload, runburst, runchaos, replay)
- Implementar bonus de alertas de anomal ́as (opcional)ı
D ́as 19–21:ı Preparaci ́on de entrega
- Completar y revisar README.md
- Preparar y practicar guion de demo (m ́aximo 8 minutos)
- Revisar y probar todos los entregables
- Congurar CI/CD si a ́un no est ́a hecho
- Realizar pruebas nales de reproducibilidad
Nota: Este cronograma es una gu ́a sugerida. Los grupos pueden ajustar el ritmo seg ́unı
sus necesidades, pero deben asegurarse de cumplir con todos los requisitos antes de la fecha
de entrega.


## 8. Entregables

### 8.1. Repositorio Git

```
El repositorio debe contener:
docker-compose.yml - Orquestaci ́on de todos los servicios
README.md - Documentaci ́on ejecutable con instrucciones completas
Schemas/ - Esquemas JSON Schema o Avro para validaci ́on
Scripts/ - Scripts de ejecuci ́on:
```
- runload.sh (o equivalente)
- runburst.sh
- runchaos.sh
- replay.sh
Servicios/ - C ́odigo fuente de cada microservicio organizado por servicio
tests/ - Tests b ́asicos (unitarios o de integraci ́on)
.github/workows/ o .gitlab-ci.yml - Conguraci ́on de CI
Makele (opcional pero recomendado) - Comandos comunes como make demo

### 8.2. Demo

```
Demo de m ́aximo 8 minutos con guion obligatorio que incluya:
```
1. Ingesti ́on (1.5 min): Mostrar generador publicando eventos en modo normal
2. Validaci ́on (1 min): Mostrar validator procesando eventos y enviando inv ́alidos a
    deadletter
3. M ́etricas (1.5 min): Mostrar agregador generando m ́etricas diarias y consulta en
    API/Dashboard
4. Falla inducida (1.5 min): Matar un consumidor y mostrar recuperaci ́on autom ́ati-
    ca
5. Recuperaci ́on (1 min): Reiniciar broker y mostrar continuidad del procesamiento
6. Replay (1.5 min): Demostrar re-procesamiento desde un punto espec ́ıco
    Total: m ́aximo 8 minutos. El guion debe estar documentado en el README o en un
archivo separado.

## 9. R ́ubrica de Evaluaci ́on

La evaluaci ́on se realizar ́a comparando las implementaciones entre grupos (mismo
problema, diferentes tecnolog ́as). La r ́ubrica es:ı


### 9.1. Correctitud Funcional (25 %)

```
Esquemas de eventos: Validaci ́on correcta de esquemas JSON (10 %)
Ventanas de agregaci ́on: Agregaci ́on correcta por ventanas diarias por regi ́on
(10 %)
M ́etricas: C ́alculo correcto de m ́etricas agregadas (5 %)
```
### 9.2. Robustez (25 %)

```
Deadletter queues: Manejo correcto de eventos inv ́alidos y fallidos (5 %)
Retry y backpressure: Pol ́tica de retries implementada y funcionando (5 %)ı
Tolerancia a fallas: Recuperaci ́on autom ́atica ante fallas de consumidores y broker
(10 %)
Idempotencia: Deduplicaci ́on correcta de eventos duplicados (5 %)
```
### 9.3. Distribuci ́on Real (20 %)

```
Paralelismo: Uso de consumer groups o equivalentes para paralelizar procesamien-
to (5 %)
Escalabilidad: Capacidad de escalar consumidores horizontalmente (5 %)
Consumer groups: Conguraci ́on correcta de grupos de consumidores (5 %)
Distribuci ́on: Arquitectura verdaderamente distribuida (no solo localhost) (5 %)
```
### 9.4. Observabilidad (15 %)

```
Logs estructurados: Logs en formato JSON con informaci ́on relevante (5 %)
M ́etricas: Throughput, error rate, lag/backlog expuestos (5 %)
Monitoreo: Capacidad de monitorear el estado del sistema (5 %)
```
### 9.5. Reproducibilidad (15 %)

```
Docker Compose: docker compose up funciona correctamente (5 %)
Scripts: Scripts de demo funcionan correctamente (5 %)
README: Documentaci ́on clara y ejecutable (3 %)
Seed: Reproducibilidad mediante seed funciona (2 %)
```

### 9.6. Bonus: Alertas de Anomal ́as (+10 %)ı

```
Implementaci ́on del t ́opico alerts.anomaly con:
Detecci ́on de anomal ́as en los datos (ej: picos inusuales, patrones an ́omalos)ı
Publicaci ́on de alertas en el t ́opico correspondiente
Explicaci ́on de la estrategia de detecci ́on en el README o durante la demo
```
## 10. Errores Comunes a Evitar

### 10.1. Errores de Dise ̃no

```
No implementar at-least-once: Asegurarse de que los consumidores conrmen
(ack) mensajes solo despu ́es de procesarlos completamente
Olvidar deduplicaci ́on: El agregador debe mantener un registro de eventid
procesados
No manejar out-of-order: Si la tecnolog ́a lo permite, considerar ordenamientoı
por timestamp antes de agregar
Deadletter sin informaci ́on: Los eventos en deadletter deben incluir el error que
caus ́o el fallo
```
### 10.2. Errores T ́ecnicos

```
No usar consumer groups: Asegurarse de congurar grupos de consumidores
para paralelismo
No congurar retries: Implementar pol ́tica de retries con l ́ı mites para evitarı
loops innitos
No exponer m ́etricas: El sistema debe permitir monitorear throughput, error
rate, y lag
Docker compose incompleto: Todos los servicios deben levantarse con un solo
comando
```
### 10.3. Errores de Demo

```
Demo demasiado larga: Respetar el tiempo m ́aximo de 8 minutos
No mostrar recuperaci ́on: La demo debe incluir fallas inducidas y recuperaci ́on
No demostrar replay: Mostrar claramente la capacidad de re-procesamiento
Falta de guion: Tener un guion claro y practicado antes de la demo
```

### 10.4. Errores de Documentaci ́on

```
README incompleto: Debe incluir instrucciones paso a paso para ejecutar el
sistema
Falta de schemas: Documentar los esquemas de eventos claramente
```
## 11. Recursos y Referencias

### 11.1. Documentaci ́on de Tecnolog ́ası

```
Kafka: https://kafka.apache.org/documentation/
Redpanda: https://docs.redpanda.com/
RabbitMQ: https://www.rabbitmq.com/documentation.html
MQTT (Mosquitto): https://mosquitto.org/documentation/
NATS JetStream: https://docs.nats.io/nats-concepts/jetstream
Redis Streams: https://redis.io/docs/data-types/streams/
```
### 11.2. Conceptos Te ́oricos

```
Sem ́anticas de entrega: at-least-once, at-most-once, exactly-once
Idempotencia y deduplicaci ́on en sistemas distribuidos
Backpressure y rate limiting
Consumer groups y particionamiento
Deadletter queues y manejo de errores
Observabilidad en sistemas distribuidos (logs, m ́etricas, traces)
```
### 11.3. HerramientasUtiles ́

```
Docker & Docker Compose: https://docs.docker.com/
JSON Schema: https://json-schema.org/
Python clients: kafka-python, pika (RabbitMQ), paho-mqtt, nats-py, redis-py
Go clients: sarama (Kafka), amqp091-go (RabbitMQ), paho.mqtt.golang, nats.go,
go-redis
Java clients: Librer ́as oı ciales de cada tecnolog ́aı
```

## 12. Fecha de Entrega

```
Fecha l ́mite:ı 30 de enero de 2026, 23:59 (hora de Chile)
Formato de entrega:
Repositorio Git con acceso para el profesor
Tag o commit espec ́ıco marcado como entrega nal
Demo programada con el profesor (presencial o remota)
```
## 13. Notas Finales

```
Este laboratorio est ́a dise ̃nado para que todos los grupos resuelvan el mismo pro-
blema, permitiendo comparaci ́on entre tecnolog ́ası
La evaluaci ́on considera tanto la correctitud funcional como la robustez y la capa-
cidad de distribuci ́on real
Se espera que los estudiantes investiguen las capacidades espec ́ıcas de su tecnolog ́aı
elegida
El bonus de alertas de anomal ́as es opcional pero recomendado para grupos queı
busquen destacar
Ante dudas, consultar con el profesor durante las horas de ocina o por correo
electr ́onico
```

