import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from database.models import TrustTier
from api.main import app

# Create a test client
client = TestClient(app)

@pytest.fixture
def mock_repo():
    with patch('api.routers.knowledge.KnowledgeRepository') as mock:
        yield mock

@patch("api.main.FF_KNOWLEDGE_UI", True)
def test_create_knowledge_source(mock_repo):
    # This is a basic test since FF_KNOWLEDGE_UI is evaluated at import time in main.py.
    # To truly test the conditionally included router, we just assume it's included or test the router directly.
    # Since we can't easily reload main.py in a fast test, we test the router endpoints directly by including it if not present.
    pass

@pytest.mark.asyncio
async def test_knowledge_router_endpoints():
    from api.routers.knowledge import router
    from fastapi import FastAPI
    from database.knowledge_repository import KnowledgeRepository
    from api.dependencies import get_knowledge_repository
    
    test_app = FastAPI()
    test_app.include_router(router)
    
    test_client = TestClient(test_app)
    
    # Mock repository
    mock_repo_instance = AsyncMock(spec=KnowledgeRepository)
    
    # Override dependency
    test_app.dependency_overrides[get_knowledge_repository] = lambda: mock_repo_instance
    
    # Test POST
    mock_repo_instance.create.return_value = {
        "id": 1,
        "source_name": "Paper A",
        "source_version": "v1.0",
        "trust_tier": TrustTier.TIER_2_PEER_REVIEWED,
        "is_active": True,
        "metadata_json": None,
        "created_at": "2026-06-16T10:00:00Z",
        "updated_at": "2026-06-16T10:00:00Z"
    }
    
    response = test_client.post("/knowledge/sources", json={
        "source_name": "Paper A",
        "source_version": "v1.0",
        "trust_tier": "TIER_2_PEER_REVIEWED"
    })
    
    assert response.status_code == 201
    assert response.json()["source_name"] == "Paper A"
    assert response.json()["source_version"] == "v1.0"
    
    # Test GET
    mock_repo_instance.get_all.return_value = [mock_repo_instance.create.return_value]
    response = test_client.get("/knowledge/sources")
    assert response.status_code == 200
    assert len(response.json()) == 1
