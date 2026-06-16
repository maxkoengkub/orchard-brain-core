import pytest
from unittest.mock import AsyncMock
from src.orchard_brain.knowledge.threshold_engine import ThresholdEngine
from database.threshold_repository import ThresholdRepository
from database.models import DynamicThresholdModel
from unittest.mock import patch

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.threshold_engine.USE_DYNAMIC_THRESHOLDS', False)
async def test_threshold_engine_fallback():
    mock_repo = AsyncMock(spec=ThresholdRepository)
    engine = ThresholdEngine(repository=mock_repo)
    
    result = await engine.get_threshold("TEMPERATURE")
    
    assert result["optimal_min"] == 25.0
    assert result["optimal_max"] == 32.0
    assert result["warn_min"] == 22.0
    assert result["warn_max"] == 35.0
    
    # Repo shouldn't be called if feature flag is false
    mock_repo.get_thresholds_by_parameter.assert_not_called()

@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.threshold_engine.USE_DYNAMIC_THRESHOLDS', True)
async def test_threshold_engine_dynamic():
    mock_repo = AsyncMock(spec=ThresholdRepository)
    
    # Mocking database dynamic threshold
    dt = DynamicThresholdModel(
        parameter_name="TEMPERATURE",
        optimal_min=24.0,
        optimal_max=30.0,
        warn_min=20.0,
        warn_max=34.0,
        critical_min=10.0,
        critical_max=40.0
    )
    mock_repo.get_thresholds_by_parameter.return_value = [dt]
    
    engine = ThresholdEngine(repository=mock_repo)
    
    result = await engine.get_threshold("TEMPERATURE")
    
    assert result["optimal_min"] == 24.0
    assert result["optimal_max"] == 30.0
    assert result["warn_min"] == 20.0
    assert result["warn_max"] == 34.0
    
    mock_repo.get_thresholds_by_parameter.assert_called_once_with("TEMPERATURE")
