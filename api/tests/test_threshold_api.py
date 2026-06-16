import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from api.main import app

@pytest.mark.asyncio
async def test_threshold_router_endpoints():
    from api.routers.thresholds import router
    from fastapi import FastAPI
    from database.threshold_repository import ThresholdRepository
    from api.dependencies import get_threshold_repository
    
    test_app = FastAPI()
    test_app.include_router(router)
    
    test_client = TestClient(test_app)
    
    mock_repo_instance = AsyncMock(spec=ThresholdRepository)
    test_app.dependency_overrides[get_threshold_repository] = lambda: mock_repo_instance
    
    mock_repo_instance.get_all_thresholds.return_value = [
        {
            "threshold_id": 1,
            "parameter_name": "TEMPERATURE",
            "optimal_min": 25.0,
            "optimal_max": 32.0,
            "warn_min": 22.0,
            "warn_max": 35.0,
            "critical_min": 15.0,
            "critical_max": 38.0,
            "confidence_score": 1.0,
            "source_id": 1,
            "evidence_id": None,
            "knowledge_epoch_id": None,
            "created_at": "2026-06-16T10:00:00Z"
        }
    ]
    
    response = test_client.get("/thresholds/")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["parameter_name"] == "TEMPERATURE"
    assert response.json()[0]["optimal_min"] == 25.0

    mock_repo_instance.get_thresholds_by_parameter.return_value = mock_repo_instance.get_all_thresholds.return_value
    
    response2 = test_client.get("/thresholds/TEMPERATURE")
    assert response2.status_code == 200
    assert len(response2.json()) == 1
