import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from api.main import app

@pytest.mark.asyncio
async def test_epoch_router_endpoints():
    from api.routers.epochs import router
    from fastapi import FastAPI
    from database.epoch_repository import EpochRepository
    from api.dependencies import get_epoch_repository
    
    test_app = FastAPI()
    test_app.include_router(router)
    
    test_client = TestClient(test_app)
    
    mock_repo_instance = AsyncMock(spec=EpochRepository)
    test_app.dependency_overrides[get_epoch_repository] = lambda: mock_repo_instance
    
    # Mocking active epoch response
    mock_repo_instance.get_active_epoch.return_value = {
        "id": 1,
        "name": "Initial Epoch",
        "description": "First epoch",
        "created_at": "2026-06-16T12:00:00Z"
    }
    
    # Mock FF_EPOCH_MANAGEMENT bypass by injecting the dependency correctly
    with patch('api.routers.epochs.EpochManager._check_flag', return_value=None):
        response = test_client.get("/epochs/active")
        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["name"] == "Initial Epoch"
