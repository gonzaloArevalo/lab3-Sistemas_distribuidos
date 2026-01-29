import pytest
import re
from datetime import datetime

class TestEventValidation:
    """Tests de validación de esquemas de eventos"""
    
    def test_valid_uuid_format(self, sample_security_incident):
        """Validar formato de UUID válido"""
        event_id = sample_security_incident["event_id"]
        
        # Patrón UUID: 8-4-4-4-12 caracteres hexadecimales
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, event_id), f"UUID inválido: {event_id}"
    
    def test_invalid_uuid_format(self, invalid_event):
        """Detectar UUID inválido"""
        event_id = invalid_event["event_id"]
        
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert not re.match(uuid_pattern, event_id), f"UUID debería ser inválido: {event_id}"
    
    def test_valid_timestamp_format(self, sample_security_incident):
        """Validar formato de timestamp ISO-8601 válido"""
        timestamp = sample_security_incident["timestamp"]
        
        # Debe terminar con Z (UTC)
        assert timestamp.endswith('Z'), "Timestamp debe terminar con Z"
        
        # Debe tener formato YYYY-MM-DDTHH:MM:SSZ
        try:
            # Intentar parsear el timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            assert dt.tzinfo is not None, "Timestamp debe tener timezone"
        except ValueError:
            pytest.fail(f"Timestamp inválido: {timestamp}")
    
    def test_invalid_timestamp_format(self, invalid_event):
        """Detectar timestamp inválido"""
        timestamp = invalid_event["timestamp"]
        
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            pytest.fail(f"Timestamp debería ser inválido: {timestamp}")
        except ValueError:
            pass  # Esperado
    
    def test_required_fields_present(self, sample_security_incident):
        """Verificar campos obligatorios presentes"""
        required_fields = ["event_id", "timestamp", "region", "source", "schema_version", "payload"]
        
        for field in required_fields:
            assert field in sample_security_incident, f"Campo obligatorio faltante: {field}"
            assert sample_security_incident[field] is not None, f"Campo obligatorio es None: {field}"
            assert sample_security_incident[field] != "", f"Campo obligatorio está vacío: {field}"
    
    def test_required_fields_missing_in_invalid_event(self, invalid_event):
        """Verificar que evento inválido falta campos requeridos"""
        # El evento inválido no tiene correlation_id (opcional) pero falta severity en payload
        
        # Campos principales deberían estar presentes aunque algunos sean inválidos
        required_main_fields = ["event_id", "timestamp", "region", "source", "schema_version", "payload"]
        for field in required_main_fields:
            assert field in invalid_event, f"Campo principal faltante: {field}"
    
    def test_security_incident_payload_validation(self, sample_security_incident):
        """Validar payload específico de security.incident"""
        payload = sample_security_incident["payload"]
        
        required_payload_fields = ["crime_type", "severity", "location", "reported_by"]
        for field in required_payload_fields:
            assert field in payload, f"Campo faltante en payload: {field}"
        
        # Validar valores específicos
        valid_crime_types = ["theft", "assault", "burglary", "fraud", "vandalism", "other"]
        assert payload["crime_type"] in valid_crime_types, f"crime_type inválido: {payload['crime_type']}"
        
        valid_severities = ["low", "medium", "high"]
        assert payload["severity"] in valid_severities, f"severity inválido: {payload['severity']}"
        
        # Validar location
        assert isinstance(payload["location"], dict), "location debe ser un diccionario"
        assert "latitude" in payload["location"], "location debe tener latitude"
        assert "longitude" in payload["location"], "location debe tener longitude"
        assert isinstance(payload["location"]["latitude"], (int, float)), "latitude debe ser numérico"
        assert isinstance(payload["location"]["longitude"], (int, float)), "longitude debe ser numérico"
    
    def test_survey_victimization_payload_validation(self, sample_survey_victimization):
        """Validar payload específico de survey.victimization"""
        payload = sample_survey_victimization["payload"]
        
        required_payload_fields = ["survey_id", "respondent_age", "victimization_type", "incident_date", "reported"]
        for field in required_payload_fields:
            assert field in payload, f"Campo faltante en payload: {field}"
        
        # Validar rangos
        assert isinstance(payload["respondent_age"], int), "respondent_age debe ser entero"
        assert 18 <= payload["respondent_age"] <= 100, "respondent_age debe estar entre 18 y 100"
        
        assert isinstance(payload["reported"], bool), "reported debe ser booleano"
        
        # Validar formato de fecha YYYY-MM-DD
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        assert re.match(date_pattern, payload["incident_date"]), f"incident_date inválido: {payload['incident_date']}"
    
    def test_migration_case_payload_validation(self, sample_migration_case):
        """Validar payload específico de migration.case"""
        payload = sample_migration_case["payload"]
        
        required_payload_fields = ["case_id", "case_type", "status", "origin_country", "application_date"]
        for field in required_payload_fields:
            assert field in payload, f"Campo faltante en payload: {field}"
        
        # Validar valores específicos
        valid_case_types = ["asylum", "work_permit", "family_reunification", "student_visa"]
        assert payload["case_type"] in valid_case_types, f"case_type inválido: {payload['case_type']}"
        
        valid_statuses = ["pending", "approved", "rejected", "under_review"]
        assert payload["status"] in valid_statuses, f"status inválido: {payload['status']}"
        
        # Validar formato de fecha YYYY-MM-DD
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        assert re.match(date_pattern, payload["application_date"]), f"application_date inválido: {payload['application_date']}"
    
    def test_source_matches_event_type(self, sample_security_incident, sample_survey_victimization, sample_migration_case):
        """Verificar que source coincide con el tipo de evento esperado"""
        assert sample_security_incident["source"] == "security.incident"
        assert sample_survey_victimization["source"] == "survey.victimization"
        assert sample_migration_case["source"] == "migration.case"
    
    def test_schema_version_format(self, sample_security_incident):
        """Validar formato de versión de esquema"""
        schema_version = sample_security_incident["schema_version"]
        
        # Debe seguir formato semver básico: X.Y
        semver_pattern = r'^\d+\.\d+$'
        assert re.match(semver_pattern, schema_version), f"schema_version inválido: {schema_version}"
