import pytest
import uuid
from datetime import datetime, timezone

@pytest.fixture
def sample_security_incident():
    """Evento válido de security.incident"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "region": "norte",
        "source": "security.incident",
        "schema_version": "1.0",
        "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
        "payload": {
            "crime_type": "theft",
            "severity": "medium",
            "location": {
                "latitude": -33.4489,
                "longitude": -70.6693
            },
            "reported_by": "citizen"
        }
    }

@pytest.fixture
def sample_survey_victimization():
    """Evento válido de survey.victimization"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "region": "sur",
        "source": "survey.victimization",
        "schema_version": "1.0",
        "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
        "payload": {
            "survey_id": f"survey-{datetime.now().year}-001",
            "respondent_age": 35,
            "victimization_type": "property_crime",
            "incident_date": "2025-01-10",
            "reported": True
        }
    }

@pytest.fixture
def sample_migration_case():
    """Evento válido de migration.case"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "region": "centro",
        "source": "migration.case",
        "schema_version": "1.0",
        "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
        "payload": {
            "case_id": f"mig-{datetime.now().year}-001",
            "case_type": "asylum",
            "status": "pending",
            "origin_country": "country-x",
            "application_date": "2025-01-01"
        }
    }

@pytest.fixture
def invalid_event():
    """Evento inválido para pruebas de validación"""
    return {
        "event_id": "invalid-uuid",
        "timestamp": "invalid-date",
        "region": "norte",
        "source": "security.incident",
        "schema_version": "1.0",
        "payload": {
            "crime_type": "theft"
        }
    }
