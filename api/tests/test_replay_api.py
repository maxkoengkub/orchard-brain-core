import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from api.main import app

@pytest.mark.asyncio
async def test_replay_router_endpoints():
    from api.routers.replay import router
    from fastapi import FastAPI
    from database.replay_repository import ReplayRepository
    from api.dependencies import get_replay_repository
    
    test_app = FastAPI()
    test_app.include_router(router)
    test_client = TestClient(test_app)
    
    mock_repo_instance = AsyncMock(spec=ReplayRepository)
    test_app.dependency_overrides[get_replay_repository] = lambda: mock_repo_instance
    
    mock_repo_instance.get_job.return_value = {
        "id": 1,
        "target_epoch_id": 1,
        "start_telemetry_time": "2026-06-01T00:00:00Z",
        "end_telemetry_time": "2026-06-02T00:00:00Z",
        "status": "COMPLETED",
        "created_at": "2026-06-16T12:00:00Z"
    }
    
    with patch('api.routers.replay.ReplayEngine._check_flag', return_value=None):
        response = test_client.get("/replay/jobs/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["status"] == "COMPLETED"
