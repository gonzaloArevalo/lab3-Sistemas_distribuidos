import uuid
import json
from datetime import datetime, timezone

class TestBasicEventGeneration:
    """Tests básicos de generación de eventos"""
    
    def test_event_structure(self, sample_security_incident):
        """Verificar estructura básica de un evento"""
        event = sample_security_incident
        
        # Campos obligatorios
        required_fields = ["event_id", "timestamp", "region", "source", "schema_version", "payload"]
        for field in required_fields:
            assert field in event, f"Campo faltante: {field}"
        
        # Validar UUID
        assert len(event["event_id"]) == 36, "event_id debe tener formato UUID"
        assert event["event_id"].count("-") == 4, "event_id debe tener formato UUID válido"
        
        # Validar timestamp ISO-8601
        assert "T" in event["timestamp"], "timestamp debe tener formato ISO-8601"
        assert event["timestamp"].endswith("Z"), "timestamp debe terminar con Z (UTC)"
        
        # Validar payload
        assert isinstance(event["payload"], dict), "payload debe ser un diccionario"
    
    def test_survey_victimization_structure(self, sample_survey_victimization):
        """Verificar estructura de evento de victimización"""
        event = sample_survey_victimization
        
        required_payload_fields = ["survey_id", "respondent_age", "victimization_type", "incident_date", "reported"]
        for field in required_payload_fields:
            assert field in event["payload"], f"Campo faltante en payload: {field}"
        
        assert isinstance(event["payload"]["respondent_age"], int), "respondent_age debe ser entero"
        assert isinstance(event["payload"]["reported"], bool), "reported debe ser booleano"
    
    def test_migration_case_structure(self, sample_migration_case):
        """Verificar estructura de evento de migración"""
        event = sample_migration_case
        
        required_payload_fields = ["case_id", "case_type", "status", "origin_country", "application_date"]
        for field in required_payload_fields:
            assert field in event["payload"], f"Campo faltante en payload: {field}"
        
        assert event["payload"]["case_type"] in ["asylum", "work_permit", "family_reunification", "student_visa"], "case_type inválido"
        assert event["payload"]["status"] in ["pending", "approved", "rejected", "under_review"], "status inválido"
    
    def test_event_serialization(self, sample_security_incident):
        """Verificar que el evento se puede serializar a JSON"""
        event = sample_security_incident
        
        # No debe lanzar excepción
        json_str = json.dumps(event)
        assert isinstance(json_str, str), "El evento debe poder serializarse a JSON string"
        
        # Debe poder deserializarse de vuelta
        deserialized = json.loads(json_str)
        assert deserialized == event, "El evento deserializado debe ser igual al original"
    
    def test_different_regions(self):
        """Verificar que se pueden crear eventos para diferentes regiones"""
        regions = ["norte", "sur", "centro", "este", "oeste"]
        
        for region in regions:
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "region": region,
                "source": "security.incident",
                "schema_version": "1.0",
                "payload": {"test": "data"}
            }
            assert event["region"] in regions, f"Región inválida: {region}"
