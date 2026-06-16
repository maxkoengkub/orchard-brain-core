import pytest
from unittest.mock import AsyncMock, patch
from src.orchard_brain.knowledge.epoch_manager import EpochManager
from database.epoch_repository import EpochRepository
from database.models import KnowledgeEpochModel, ActiveEpochPointerModel
from datetime import datetime

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.epoch_manager.FF_EPOCH_MANAGEMENT', False)
async def test_epoch_manager_flag_disabled():
    mock_repo = AsyncMock(spec=EpochRepository)
    manager = EpochManager(repository=mock_repo)
    
    with pytest.raises(RuntimeError, match="FF_EPOCH_MANAGEMENT is disabled."):
        await manager.get_active_epoch()

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.epoch_manager.FF_EPOCH_MANAGEMENT', True)
async def test_epoch_manager_flag_enabled():
    mock_repo = AsyncMock(spec=EpochRepository)
    mock_epoch = KnowledgeEpochModel(id=1, name="Test Epoch", description="Test")
    mock_repo.get_active_epoch.return_value = mock_epoch
    
    manager = EpochManager(repository=mock_repo)
    
    result = await manager.get_active_epoch()
    assert result.id == 1
    assert result.name == "Test Epoch"
    mock_repo.get_active_epoch.assert_called_once()
