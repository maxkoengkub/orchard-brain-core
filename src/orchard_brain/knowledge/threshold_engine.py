from typing import Optional, Dict, Any, TypedDict
from database.threshold_repository import ThresholdRepository
from database.epoch_repository import EpochRepository
from database.config import USE_DYNAMIC_THRESHOLDS
import src.orchard_brain._thresholds as static_thresholds
from src.orchard_brain.knowledge.epoch_manager import EpochManager

PARAM_TEMPERATURE = "TEMPERATURE"
PARAM_HUMIDITY = "HUMIDITY"
PARAM_EC = "EC"
PARAM_PH = "PH"
PARAM_VPD = "VPD"
PARAM_PHYTOPHTHORA = "PHYTOPHTHORA"

class ThresholdBounds(TypedDict, total=False):
    optimal_min: Optional[float]
    optimal_max: Optional[float]
    warn_min: Optional[float]
    warn_max: Optional[float]
    critical_min: Optional[float]
    critical_max: Optional[float]

ThresholdMap = Dict[str, ThresholdBounds]

class ThresholdEngine:
    """Centralized service for threshold resolution.
    
    Checks USE_DYNAMIC_THRESHOLDS feature flag.
    Provides typed dictionaries to completely isolate OrchardBrain from SQLAlchemy ORM logic.
    Supports partial merging with _thresholds.py singletons.
    """
    
    def __init__(self, repository: ThresholdRepository):
        self.repository = repository
        
        # Mapping parameter names to static threshold singletons for fallback
        self._static_map = {
            PARAM_TEMPERATURE: static_thresholds.TEMPERATURE,
            PARAM_HUMIDITY: static_thresholds.HUMIDITY,
            PARAM_EC: static_thresholds.EC,
            PARAM_PH: static_thresholds.PH,
            PARAM_VPD: static_thresholds.VPD,
            PARAM_PHYTOPHTHORA: static_thresholds.PHYTOPHTHORA
        }

    async def get_all_thresholds(self, epoch_id: Optional[int] = None) -> ThresholdMap:
        """Resolve all parameters into a unified ThresholdMap.
        
        Resolves active epoch pointer if epoch_id is None.
        Merges static defaults with dynamic DB overrides.
        """
        threshold_map: ThresholdMap = {}
        
        # Step 1: Populate all defaults
        for param in self._static_map.keys():
            threshold_map[param] = self._get_static_fallback(param)
            
        if not USE_DYNAMIC_THRESHOLDS:
            return threshold_map
            
        # Step 2: Resolve epoch_id if not provided explicitly
        resolved_epoch_id = epoch_id
        if resolved_epoch_id is None:
            # We instantiate EpochManager here to avoid circular dependency.
            epoch_repo = EpochRepository(self.repository.session)
            epoch_manager = EpochManager(epoch_repo)
            try:
                active_epoch = await epoch_manager.get_active_epoch()
                if active_epoch:
                    resolved_epoch_id = active_epoch.id
            except RuntimeError:
                pass # FF_EPOCH_MANAGEMENT might be disabled
                
        # Step 3: Fetch overrides and merge
        db_thresholds = await self.repository.get_all_thresholds(epoch_id=resolved_epoch_id)
        
        # Merge the partial overrides
        # We process in order they are returned. In a real system, we'd sort by confidence.
        # Here we just take the first one we find per parameter if multiple exist.
        seen_params = set()
        for dt in db_thresholds:
            param = dt.parameter_name
            if param not in seen_params:
                seen_params.add(param)
                threshold_map[param] = {
                    "optimal_min": dt.optimal_min,
                    "optimal_max": dt.optimal_max,
                    "warn_min": dt.warn_min,
                    "warn_max": dt.warn_max,
                    "critical_min": dt.critical_min,
                    "critical_max": dt.critical_max
                }
                
        return threshold_map

    async def get_threshold(self, parameter_name: str) -> Dict[str, Optional[float]]:
        """Resolve a threshold for a given parameter (Legacy single-fetch mode)."""
        static_fallback = self._get_static_fallback(parameter_name)
        
        if not USE_DYNAMIC_THRESHOLDS:
            return static_fallback
            
        db_thresholds = await self.repository.get_thresholds_by_parameter(parameter_name)
        
        if not db_thresholds:
            return static_fallback
            
        dt = db_thresholds[0]
        
        return {
            "optimal_min": dt.optimal_min,
            "optimal_max": dt.optimal_max,
            "warn_min": dt.warn_min,
            "warn_max": dt.warn_max,
            "critical_min": dt.critical_min,
            "critical_max": dt.critical_max
        }

    def _get_static_fallback(self, parameter_name: str) -> ThresholdBounds:
        static_obj = self._static_map.get(parameter_name)
        if not static_obj:
            return {}
            
        result: ThresholdBounds = {
            "optimal_min": None,
            "optimal_max": None,
            "warn_min": None,
            "warn_max": None,
            "critical_min": None,
            "critical_max": None
        }
        
        if parameter_name == PARAM_PHYTOPHTHORA:
            result["warn_max"] = getattr(static_obj, "moisture_warn", None)
            result["critical_max"] = getattr(static_obj, "moisture_critical", None)
            result["optimal_min"] = getattr(static_obj, "temp_favour_low", None)
            result["optimal_max"] = getattr(static_obj, "temp_favour_high", None)
        else:
            result["optimal_min"] = getattr(static_obj, "optimal_low", None)
            result["optimal_max"] = getattr(static_obj, "optimal_high", None)
            result["warn_min"] = getattr(static_obj, "warn_low", None)
            result["warn_max"] = getattr(static_obj, "warn_high", None)
            result["critical_min"] = getattr(static_obj, "critical_low", None)
            result["critical_max"] = getattr(static_obj, "critical_high", None)
            
        return result
