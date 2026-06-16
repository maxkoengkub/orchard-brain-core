import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from api.main import app

@pytest.mark.asyncio
async def test_evidence_router_endpoints():
    from api.routers.evidence import router
    from fastapi import FastAPI
    from database.evidence_repository import EvidenceRepository
    from api.dependencies import get_evidence_repository
    
    test_app = FastAPI()
    test_app.include_router(router)
    
    test_client = TestClient(test_app)
    
    mock_repo_instance = AsyncMock(spec=EvidenceRepository)
    test_app.dependency_overrides[get_evidence_repository] = lambda: mock_repo_instance
    
    mock_repo_instance.get_evidence_for_risk.return_value = [
        {
            "id": 1,
            "risk_id": 100,
            "source_id": 5,
            "knowledge_epoch_id": None,
            "rule_key": "rule_a",
            "rule_version": "v1",
            "confidence_weight": 0.8,
            "context_json": None,
            "created_at": "2026-06-16T10:00:00Z"
        }
    ]
    
    response = test_client.get("/evidence/risk/100")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["risk_id"] == 100
    assert response.json()[0]["rule_key"] == "rule_a"

    # Verify no POST endpoints exist
    post_response = test_client.post("/evidence/risk/100", json={})
    assert post_response.status_code == 405  # Method Not Allowed
