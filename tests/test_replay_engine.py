import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from src.orchard_brain.knowledge.replay_engine import ReplayEngine
from database.replay_repository import ReplayRepository

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.replay_engine.FF_REPLAY_ENGINE', False)
async def test_replay_engine_flag_disabled():
    mock_repo = AsyncMock(spec=ReplayRepository)
    engine = ReplayEngine(repository=mock_repo)
    
    with pytest.raises(RuntimeError, match="FF_REPLAY_ENGINE is disabled."):
        await engine.start_job(1, datetime.now(timezone.utc), datetime.now(timezone.utc))

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.replay_engine.FF_REPLAY_ENGINE', True)
async def test_replay_engine_flag_enabled():
    mock_repo = AsyncMock(spec=ReplayRepository)
    engine = ReplayEngine(repository=mock_repo)
    
    # Mocking
    mock_job = AsyncMock()
    mock_repo.create_job.return_value = mock_job
    mock_repo.get_job.return_value = mock_job
    
    await engine.start_job(1, datetime.now(timezone.utc), datetime.now(timezone.utc))
    mock_repo.create_job.assert_called_once()
    
    mock_telemetry = [{"timestamp": datetime.now(timezone.utc), "temp": 25.0, "hum": 60.0, "ec": 1.2, "ph": 6.0}]
    await engine.run_job(1, mock_telemetry)
    
    # Verify OrchardBrain results are saved
    mock_repo.save_result.assert_called_once()
    mock_repo.update_job_status.assert_any_call(1, "RUNNING")
    mock_repo.update_job_status.assert_any_call(1, "COMPLETED")
