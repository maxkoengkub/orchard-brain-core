import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.orchard_brain import OrchardBrain
from src.orchard_brain.knowledge.threshold_engine import (
    ThresholdEngine,
    ThresholdMap,
    PARAM_TEMPERATURE,
    PARAM_HUMIDITY,
    PARAM_EC,
    PARAM_PH,
    PARAM_VPD,
    PARAM_PHYTOPHTHORA
)
from src.orchard_brain._thresholds import TEMPERATURE, HUMIDITY, EC, PH, VPD, PHYTOPHTHORA
from database.threshold_repository import ThresholdRepository
from database.models import DynamicThresholdModel


# 1. Dynamic Mutation Proof (Unit)
def test_dynamic_mutation_proof():
    brain = OrchardBrain()
    
    # Inject a mock ThresholdMap artificially lowering the critical temperature maximum
    mock_map: ThresholdMap = {
        PARAM_TEMPERATURE: {
            "critical_max": 25.0
        }
    }
    
    # Input 26.0 which normally passes (static critical is 35.0+) but should fail here
    result = brain.evaluate_raw(
        temperature=26.0,
        humidity=50.0,
        ec=1.2,
        ph=6.0,
        thresholds=mock_map
    )
    
    # Assert output explicitly triggers a heat risk
    risk_names = [r["risk"].lower() for r in result["risks"]]
    assert any("temperature" in r or "heat" in r for r in risk_names), \
        "Expected a critical heat/temperature risk."
    assert result["health_score"] < 100, "Health score should be penalized."


# 2. Partial Merge Validation (Unit)
@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.threshold_engine.USE_DYNAMIC_THRESHOLDS', True)
async def test_partial_merge_validation():
    mock_repo = AsyncMock(spec=ThresholdRepository)
    
    # Database containing only one row (TEMPERATURE)
    mock_model = MagicMock(spec=DynamicThresholdModel)
    mock_model.parameter_name = PARAM_TEMPERATURE
    mock_model.optimal_min = None
    mock_model.optimal_max = 27.5
    mock_model.warn_min = None
    mock_model.warn_max = None
    mock_model.critical_min = None
    mock_model.critical_max = None
    
    mock_repo.get_all_thresholds.return_value = [mock_model]
    
    engine = ThresholdEngine(mock_repo)
    result = await engine.get_all_thresholds(epoch_id=1)
    
    # Assert output correctly contains dynamic TEMPERATURE alongside static defaults
    assert result[PARAM_TEMPERATURE]["optimal_max"] == 27.5
    assert result[PARAM_HUMIDITY]["optimal_max"] == HUMIDITY.optimal_high


# 3. Fallback Parity Proof (Unit)
def test_fallback_parity_proof():
    brain = OrchardBrain()
    
    # Explicit StaticThresholdMap mirroring static defaults
    StaticThresholdMap: ThresholdMap = {
        PARAM_TEMPERATURE: {
            "optimal_min": TEMPERATURE.optimal_low,
            "optimal_max": TEMPERATURE.optimal_high,
            "warn_min": TEMPERATURE.warn_low,
            "warn_max": TEMPERATURE.warn_high,
            "critical_min": TEMPERATURE.critical_low,
            "critical_max": TEMPERATURE.critical_high
        },
        PARAM_HUMIDITY: {
            "optimal_min": HUMIDITY.optimal_low,
            "optimal_max": HUMIDITY.optimal_high,
            "warn_min": HUMIDITY.warn_low,
            "warn_max": HUMIDITY.warn_high,
            "critical_min": HUMIDITY.critical_low,
            "critical_max": HUMIDITY.critical_high
        },
        PARAM_EC: {
            "optimal_min": EC.optimal_low,
            "optimal_max": EC.optimal_high,
            "warn_min": EC.warn_low,
            "warn_max": EC.warn_high,
            "critical_min": EC.critical_low,
            "critical_max": EC.critical_high
        },
        PARAM_PH: {
            "optimal_min": PH.optimal_low,
            "optimal_max": PH.optimal_high,
            "warn_min": PH.warn_low,
            "warn_max": PH.warn_high,
            "critical_min": PH.critical_low,
            "critical_max": PH.critical_high
        },
        PARAM_VPD: {
            "optimal_max": VPD.optimal_high,
            "warn_min": None,
            "warn_max": VPD.warn_high,
            "critical_min": None,
            "critical_max": VPD.critical_high
        },
        PARAM_PHYTOPHTHORA: {
            "optimal_min": PHYTOPHTHORA.temp_favour_low,
            "optimal_max": PHYTOPHTHORA.temp_favour_high,
            "warn_max": PHYTOPHTHORA.moisture_warn,
            "critical_max": PHYTOPHTHORA.moisture_critical
        }
    }
    
    A = brain.evaluate_raw(temperature=28.0, humidity=60.0, ec=1.5, ph=6.2, thresholds=None)
    B = brain.evaluate_raw(temperature=28.0, humidity=60.0, ec=1.5, ph=6.2, thresholds=StaticThresholdMap)
    
    assert A == B


# 4. Epoch Resolution Parity Test (Integration)
@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.threshold_engine.USE_DYNAMIC_THRESHOLDS', True)
@patch('src.orchard_brain.knowledge.threshold_engine.EpochManager')
@patch('src.orchard_brain.engine.ThresholdRepository')
@patch('src.orchard_brain.engine.AsyncSessionLocal')
async def test_epoch_resolution_parity(mock_session, mock_repo_class, mock_epoch_manager_class):
    mock_session.return_value.__aenter__.return_value = MagicMock()
    mock_session.return_value.__aexit__.return_value = None
    
    # Setup EpochManager to return epoch 7
    mock_epoch_manager_instance = mock_epoch_manager_class.return_value
    mock_epoch_manager_instance.get_active_epoch = AsyncMock(return_value=MagicMock(id=7))
    
    # Setup ThresholdRepository
    mock_repo_instance = mock_repo_class.return_value
    mock_model = MagicMock(spec=DynamicThresholdModel)
    mock_model.parameter_name = PARAM_TEMPERATURE
    mock_model.optimal_min = None
    mock_model.optimal_max = 30.0
    mock_model.warn_min = None
    mock_model.warn_max = None
    mock_model.critical_min = None
    mock_model.critical_max = None
    mock_repo_instance.get_all_thresholds = AsyncMock(return_value=[mock_model])
    
    brain = OrchardBrain()
    
    class DummyReading:
        temperature = 26.0
        humidity = 50.0
        ec = 1.2
        ph = 6.0
        
    reading = DummyReading()
    
    # Path A (Production) resolves epoch pointer
    result_production = await brain.evaluate_async(reading, epoch_id=None)
    
    # Path B (Replay) explicitly passes epoch 7
    result_replay = await brain.evaluate_async(reading, epoch_id=7)
    
    # Assert output is strictly identical proving convergence
    assert result_production == result_replay


# 5. Epoch Resolution Divergence (Integration)
@pytest.mark.asyncio
@patch('src.orchard_brain.knowledge.threshold_engine.USE_DYNAMIC_THRESHOLDS', True)
@patch('src.orchard_brain.engine.ThresholdRepository')
@patch('src.orchard_brain.engine.AsyncSessionLocal')
async def test_epoch_resolution_divergence(mock_session, mock_repo_class):
    mock_session.return_value.__aenter__.return_value = MagicMock()
    mock_session.return_value.__aexit__.return_value = None
    
    mock_repo_instance = mock_repo_class.return_value
    
    def side_effect_get_all(epoch_id=None):
        if epoch_id == 7:
            # Safe bounds
            mock_7 = MagicMock(spec=DynamicThresholdModel)
            mock_7.parameter_name = PARAM_TEMPERATURE
            mock_7.optimal_min = None
            mock_7.optimal_max = None
            mock_7.warn_min = None
            mock_7.warn_max = None
            mock_7.critical_min = None
            mock_7.critical_max = 35.0
            return [mock_7]
        elif epoch_id == 8:
            # Stricter bounds
            mock_8 = MagicMock(spec=DynamicThresholdModel)
            mock_8.parameter_name = PARAM_TEMPERATURE
            mock_8.optimal_min = None
            mock_8.optimal_max = None
            mock_8.warn_min = None
            mock_8.warn_max = None
            mock_8.critical_min = None
            mock_8.critical_max = 25.0
            return [mock_8]
        return []
        
    mock_repo_instance.get_all_thresholds = AsyncMock(side_effect=side_effect_get_all)
    
    brain = OrchardBrain()
    
    class DummyReading:
        temperature = 26.0
        humidity = 50.0
        ec = 1.2
        ph = 6.0
        
    reading = DummyReading()
    
    result_epoch_7 = await brain.evaluate_async(reading, epoch_id=7)
    result_epoch_8 = await brain.evaluate_async(reading, epoch_id=8)
    
    # Assert they evaluated differently due to the divergent threshold maps
    assert result_epoch_7 != result_epoch_8
    
    # Assert critical risk triggers in Epoch 8 but not Epoch 7
    risk_types_7 = [r["risk"] for r in result_epoch_7["risks"] if r["severity"] == "critical"]
    risk_types_8 = [r["risk"] for r in result_epoch_8["risks"] if r["severity"] == "critical"]
    
    assert "heat_stress" not in risk_types_7
    assert "heat_stress" in risk_types_8
