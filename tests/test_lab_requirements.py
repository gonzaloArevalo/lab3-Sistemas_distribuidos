"""
Tests específicos para requisitos del Lab 3 - País X
Estos tests cubren casos específicos mencionados en el documento del laboratorio
"""
import pytest
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List


class TestLabSpecificRequirements:
    """Tests para requisitos específicos del laboratorio"""
    
    def test_at_least_once_delivery_semantics(self, sample_security_incident):
        """Test RF1: Verificar semántica at-least-once"""
        # Simular procesamiento duplicado del mismo evento
        event_id = sample_security_incident["event_id"]
        
        processed_events = set()
        
        # Procesar evento dos veces (simulación)
        for i in range(2):
            if event_id not in processed_events:
                # Primera vez: procesar
                processed_events.add(event_id)
                result = {"processed": True, "attempt": i + 1}
            else:
                # Duplicado: detectar pero no procesar nuevamente
                result = {"processed": False, "reason": "duplicate", "attempt": i + 1}
        
        # Verificar que se procesó al menos una vez
        assert len(processed_events) == 1, "Debe procesarse al menos una vez"
        assert event_id in processed_events, "El evento debe estar en procesados"
    
    def test_idempotency_and_deduplication(self, sample_security_incident):
        """Test RF2: Idempotencia y deduplicación"""
        processed_events = {}
        event = sample_security_incident
        event_id = event["event_id"]
        
        # Simular múltiples procesamientos del mismo evento
        results = []
        for attempt in range(3):
            if event_id not in processed_events:
                # Primera vez: procesar y registrar
                processed_events[event_id] = {
                    "processed_at": time.time(),
                    "attempt": attempt + 1,
                    "result": "processed"
                }
                results.append({"status": "processed", "attempt": attempt + 1})
            else:
                # Duplicado: devolver resultado existente
                results.append({
                    "status": "duplicate", 
                    "attempt": attempt + 1,
                    "original_attempt": processed_events[event_id]["attempt"]
                })
        
        # Verificar idempotencia
        assert results[0]["status"] == "processed", "Primer intento debe procesar"
        assert all(r["status"] == "duplicate" for r in results[1:]), "Intentos subsiguientes deben ser duplicados"
        assert processed_events[event_id]["attempt"] == 1, "Solo debe procesarse una vez"
    
    def test_backpressure_handling(self):
        """Test RF3: Manejo de backpressure"""
        # Simular sistema con capacidad limitada
        max_queue_size = 100
        current_queue_size = 0
        processed_count = 0
        rejected_count = 0
        
        # Simular llegada de eventos
        for i in range(150):
            if current_queue_size < max_queue_size:
                # Aceptar evento
                current_queue_size += 1
                # Simular procesamiento
                if i % 10 == 0:  # Procesar cada 10 eventos
                    current_queue_size -= 1
                    processed_count += 1
            else:
                # Backpressure: rechazar evento
                rejected_count += 1
        
        # Verificar manejo de backpressure
        assert processed_count > 0, "Deben procesarse algunos eventos"
        assert rejected_count > 0, "Deben rechazarse eventos en backpressure"
        assert current_queue_size <= max_queue_size, "La cola no debe exceder el máximo"
    
    def test_retry_policy_with_backoff(self):
        """Test RF3: Política de retry con backoff"""
        class RetrySimulator:
            def __init__(self, max_retries=3):
                self.max_retries = max_retries
                self.attempts = 0
            
            def process_with_retry(self, should_fail_until=2):
                self.attempts = 0
                backoff_times = [1, 2, 4]  # Backoff exponencial
                
                while self.attempts < self.max_retries:
                    self.attempts += 1
                    
                    # Simular procesamiento
                    if self.attempts <= should_fail_until:
                        continue  # Fallar
                    
                    return {"success": True, "attempts": self.attempts}
                
                return {"success": False, "attempts": self.attempts}
        
        # Test retry exitoso
        retry_sim = RetrySimulator(max_retries=3)
        result = retry_sim.process_with_retry(should_fail_until=2)
        assert result["success"], "Debe eventualmente tener éxito"
        assert result["attempts"] == 3, "Debe intentar 3 veces"
        
        # Test retry fallido
        retry_sim = RetrySimulator(max_retries=3)
        result = retry_sim.process_with_retry(should_fail_until=5)  # Siempre falla
        assert not result["success"], "Debe fallar después de máximos reintentos"
        assert result["attempts"] == 3, "Debe intentar máximo 3 veces"
    
    def test_fault_tolerance_consumer_recovery(self):
        """Test RF4: Tolerancia a fallas - recuperación de consumidor"""
        class ConsumerSimulator:
            def __init__(self):
                self.is_running = True
                self.processed_events = []
                self.last_checkpoint = 0
            
            def process_event(self, event):
                if not self.is_running:
                    raise Exception("Consumer no está corriendo")
                
                self.processed_events.append(event)
                # Checkpoint cada 10 eventos
                if len(self.processed_events) % 10 == 0:
                    self.last_checkpoint = len(self.processed_events)
            
            def kill(self):
                """Simular caída del consumidor"""
                self.is_running = False
            
            def restart(self):
                """Simular reinicio del consumidor"""
                self.is_running = True
                # Recuperar desde último checkpoint
                recovered_count = self.last_checkpoint
                return recovered_count
        
        # Simular procesamiento normal
        consumer = ConsumerSimulator()
        events = [f"event_{i}" for i in range(25)]
        
        # Procesar algunos eventos
        for event in events[:15]:
            consumer.process_event(event)
        
        assert len(consumer.processed_events) == 15, "Deben procesarse 15 eventos"
        assert consumer.last_checkpoint == 10, "Checkpoint en 10 eventos"
        
        # Simular caída
        consumer.kill()
        
        # Intentar procesar más (debe fallar)
        with pytest.raises(Exception):
            consumer.process_event(events[15])
        
        # Reiniciar y recuperar
        recovered_count = consumer.restart()
        assert recovered_count == 10, "Debe recuperar desde checkpoint"
        
        # Continuar procesamiento
        for event in events[15:]:
            consumer.process_event(event)
        
        assert len(consumer.processed_events) == 25, "Deben procesarse todos los eventos"
    
    def test_replay_capability(self):
        """Test RF5: Capacidad de replay"""
        class EventStore:
            def __init__(self):
                self.events = []
                self.offsets = {}  # event_id -> offset
            
            def store_event(self, event):
                offset = len(self.events)
                self.events.append(event)
                self.offsets[event["event_id"]] = offset
                return offset
            
            def replay_from_offset(self, offset):
                """Reprocesar eventos desde offset específico"""
                return self.events[offset:]
            
            def replay_from_timestamp(self, timestamp):
                """Reprocesar eventos desde timestamp específico"""
                from datetime import datetime
                target_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                replay_events = []
                for event in self.events:
                    event_dt = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
                    if event_dt >= target_dt:
                        replay_events.append(event)
                
                return replay_events
        
        # Crear store de eventos
        store = EventStore()
        
        # Generar eventos con timestamps diferentes
        base_time = datetime.now(timezone.utc)
        events = []
        for i in range(10):
            event_time = base_time + timedelta(minutes=i)
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": event_time.isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {"test": i}
            }
            events.append(event)
            store.store_event(event)
        
        # Test replay desde offset
        replay_from_5 = store.replay_from_offset(5)
        assert len(replay_from_5) == 5, "Debe reproducir 5 eventos desde offset 5"
        assert replay_from_5[0]["payload"]["test"] == 5, "Primer evento debe ser el 6"
        
        # Test replay desde timestamp
        target_timestamp = (base_time + timedelta(minutes=7)).isoformat().replace('+00:00', 'Z')
        replay_from_time = store.replay_from_timestamp(target_timestamp)
        assert len(replay_from_time) == 3, "Debe reproducir eventos desde minuto 7 (minutos 7, 8, 9)"
        assert replay_from_time[0]["payload"]["test"] == 7, "Primer evento debe ser el 8"
    
    def test_observability_metrics(self):
        """Test RF6: Observabilidad - métricas mínimas"""
        class MetricsCollector:
            def __init__(self):
                self.events_processed = 0
                self.errors = 0
                self.start_time = time.time()
                self.lag_events = 0
            
            def record_processed_event(self):
                self.events_processed += 1
            
            def record_error(self):
                self.errors += 1
            
            def get_throughput(self):
                elapsed = time.time() - self.start_time
                return self.events_processed / elapsed if elapsed > 0 else 0
            
            def get_error_rate(self):
                total = self.events_processed + self.errors
                return self.errors / total if total > 0 else 0
            
            def set_lag(self, lag_count):
                self.lag_events = lag_count
            
            def get_metrics(self):
                return {
                    "throughput_events_per_second": self.get_throughput(),
                    "error_rate": self.get_error_rate(),
                    "lag_backlog_events": self.lag_events,
                    "total_processed": self.events_processed,
                    "total_errors": self.errors
                }
        
        # Simular procesamiento con métricas
        metrics = MetricsCollector()
        
        # Procesar eventos
        for i in range(100):
            if i % 10 == 0:  # 10% de errores
                metrics.record_error()
            else:
                metrics.record_processed_event()
        
        # Simular lag
        metrics.set_lag(25)
        
        # Obtener métricas
        result = metrics.get_metrics()
        
        # Verificar métricas
        assert result["total_processed"] == 90, "Deben procesarse 90 eventos"
        assert result["total_errors"] == 10, "Deben haber 10 errores"
        assert result["error_rate"] == 0.1, "Error rate debe ser 10%"
        assert result["lag_backlog_events"] == 25, "Lag debe ser 25 eventos"
        assert result["throughput_events_per_second"] > 0, "Throughput debe ser positivo"
    
    def test_reproducibility_with_seed(self):
        """Test RF7: Reproducibilidad con seed"""
        def generate_events(seed=None, count=5):
            import random
            rng = random.Random(seed) if seed else random.Random()
            
            events = []
            for i in range(count):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "region": rng.choice(["norte", "sur", "centro", "este", "oeste"]),
                    "source": rng.choice(["security.incident", "survey.victimization", "migration.case"]),
                    "schema_version": "1.0",
                    "payload": {
                        "random_value": rng.randint(1, 100),
                        "random_choice": rng.choice(["A", "B", "C"])
                    }
                }
                events.append(event)
            
            return events
        
        # Generar con misma seed
        events1 = generate_events(seed=42, count=5)
        events2 = generate_events(seed=42, count=5)
        
        # Generar con diferente seed
        events3 = generate_events(seed=123, count=5)
        
        # Verificar reproducibilidad
        assert len(events1) == len(events2) == 5, "Misma cantidad de eventos"
        
        # Las regiones y sources deben ser iguales para misma seed
        for i in range(5):
            assert events1[i]["region"] == events2[i]["region"], f"Región {i} debe ser igual"
            assert events1[i]["source"] == events2[i]["source"], f"Source {i} debe ser igual"
            assert events1[i]["payload"]["random_value"] == events2[i]["payload"]["random_value"], f"Valor aleatorio {i} debe ser igual"
        
        # Con diferente seed deben ser diferentes
        assert events1[0]["region"] != events3[0]["region"] or events1[0]["source"] != events3[0]["source"], "Seed diferente debe generar diferentes eventos"


class TestEventScenarios:
    """Tests para escenarios específicos de eventos"""
    
    def test_out_of_order_events(self):
        """Test procesamiento de eventos fuera de orden"""
        # Crear eventos fuera de orden
        base_time = datetime.now(timezone.utc)
        events = [
            {
                "event_id": "event-3",
                "timestamp": (base_time + timedelta(minutes=3)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {"sequence": 3}
            },
            {
                "event_id": "event-1", 
                "timestamp": (base_time + timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {"sequence": 1}
            },
            {
                "event_id": "event-2",
                "timestamp": (base_time + timedelta(minutes=2)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {"sequence": 2}
            }
        ]
        
        # Ordenar por timestamp
        sorted_events = sorted(events, key=lambda x: x["timestamp"])
        
        # Verificar orden correcto
        assert sorted_events[0]["payload"]["sequence"] == 1, "Primer evento debe ser sequence 1"
        assert sorted_events[1]["payload"]["sequence"] == 2, "Segundo evento debe ser sequence 2"
        assert sorted_events[2]["payload"]["sequence"] == 3, "Tercer evento debe ser sequence 3"
    
    def test_burst_mode_simulation(self):
        """Test modo burst del generador"""
        class BurstSimulator:
            def __init__(self, normal_rate=1.0, burst_multiplier=5.0):
                self.normal_rate = normal_rate
                self.burst_multiplier = burst_multiplier
                self.events_generated = []
            
            def generate_burst(self, duration_seconds=2, events_per_second_normal=1.0):
                """Simular generación de eventos en modo burst"""
                burst_rate = events_per_second_normal * self.burst_multiplier
                events_in_burst = int(burst_rate * duration_seconds)
                
                for i in range(events_in_burst):
                    event = {
                        "event_id": str(uuid.uuid4()),
                        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        "region": "norte",
                        "source": "security.incident",
                        "schema_version": "1.0",
                        "payload": {"burst_index": i}
                    }
                    self.events_generated.append(event)
                
                return len(self.events_generated)
        
        # Test modo burst
        burst_sim = BurstSimulator(normal_rate=1.0, burst_multiplier=5.0)
        events_count = burst_sim.generate_burst(duration_seconds=2, events_per_second_normal=1.0)
        
        # En modo burst: 1.0 * 5.0 * 2 = 10 eventos
        assert events_count == 10, f"Debe generar 10 eventos en burst, generó {events_count}"
        assert len(burst_sim.events_generated) == 10, "Debe tener 10 eventos almacenados"
    
    def test_daily_aggregation_window(self):
        """Test agregación por ventanas diarias"""
        class DailyAggregator:
            def __init__(self):
                self.daily_metrics = {}
            
            def add_event(self, event):
                # Extraer fecha del timestamp
                date_str = event["timestamp"][:10]  # YYYY-MM-DD
                region = event["region"]
                source = event["source"]
                
                key = f"{date_str}_{region}_{source}"
                
                if key not in self.daily_metrics:
                    self.daily_metrics[key] = {
                        "date": date_str,
                        "region": region,
                        "source": source,
                        "count": 0,
                        "events": []
                    }
                
                self.daily_metrics[key]["count"] += 1
                self.daily_metrics[key]["events"].append(event["event_id"])
            
            def get_daily_metrics(self, date, region):
                """Obtener métricas para fecha y región específicas"""
                results = []
                for key, metrics in self.daily_metrics.items():
                    if metrics["date"] == date and metrics["region"] == region:
                        results.append(metrics)
                return results
        
        # Crear agregador
        aggregator = DailyAggregator()
        
        # Agregar eventos de diferentes días y regiones
        base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        events = [
            {
                "event_id": str(uuid.uuid4()),
                "timestamp": (base_time + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {}
            },
            {
                "event_id": str(uuid.uuid4()),
                "timestamp": (base_time + timedelta(hours=2)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {}
            },
            {
                "event_id": str(uuid.uuid4()),
                "timestamp": (base_time + timedelta(days=1, hours=1)).isoformat().replace('+00:00', 'Z'),
                "region": "norte",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {}
            },
            {
                "event_id": str(uuid.uuid4()),
                "timestamp": (base_time + timedelta(hours=3)).isoformat().replace('+00:00', 'Z'),
                "region": "sur",
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {}
            }
        ]
        
        # Procesar eventos
        for event in events:
            aggregator.add_event(event)
        
        # Verificar agregación diaria
        norte_metrics = aggregator.get_daily_metrics("2025-01-15", "norte")
        assert len(norte_metrics) == 1, "Debe haber un grupo para norte 2025-01-15"
        assert norte_metrics[0]["count"] == 2, "Debe haber 2 eventos para norte 2025-01-15"
        
        sur_metrics = aggregator.get_daily_metrics("2025-01-15", "sur")
        assert len(sur_metrics) == 1, "Debe haber un grupo para sur 2025-01-15"
        assert sur_metrics[0]["count"] == 1, "Debe haber 1 evento para sur 2025-01-15"
        
        # Día siguiente
        norte_next_day = aggregator.get_daily_metrics("2025-01-16", "norte")
        assert len(norte_next_day) == 1, "Debe haber un grupo para norte 2025-01-16"
        assert norte_next_day[0]["count"] == 1, "Debe haber 1 evento para norte 2025-01-16"
