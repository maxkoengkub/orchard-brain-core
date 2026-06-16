from typing import Optional, Dict, Any
from database.threshold_repository import ThresholdRepository
from database.config import USE_DYNAMIC_THRESHOLDS
import src.orchard_brain._thresholds as static_thresholds

class ThresholdEngine:
    """Centralized service for threshold resolution.
    
    Checks USE_DYNAMIC_THRESHOLDS feature flag.
    If active, fetches from the database.
    If missing or disabled, falls back to the static dataclasses in _thresholds.py.
    """
    
    def __init__(self, repository: ThresholdRepository):
        self.repository = repository
        
        # Mapping parameter names to static threshold singletons for fallback
        self._static_map = {
            "TEMPERATURE": static_thresholds.TEMPERATURE,
            "HUMIDITY": static_thresholds.HUMIDITY,
            "EC": static_thresholds.EC,
            "PH": static_thresholds.PH,
            "VPD": static_thresholds.VPD,
            "PHYTOPHTHORA": static_thresholds.PHYTOPHTHORA
        }

    async def get_threshold(self, parameter_name: str) -> Dict[str, Optional[float]]:
        """Resolve a threshold for a given parameter.
        
        If USE_DYNAMIC_THRESHOLDS is true and an active evidence-backed
        threshold exists, return it. Otherwise, return the static fallback.
        """
        # Shadow-mode / Fallback baseline
        static_fallback = self._get_static_fallback(parameter_name)
        
        if not USE_DYNAMIC_THRESHOLDS:
            return static_fallback
            
        # Try fetching dynamic threshold
        db_thresholds = await self.repository.get_thresholds_by_parameter(parameter_name)
        
        if not db_thresholds:
            return static_fallback
            
        # Assume the most recent/relevant one is returned. For now, take the first.
        # In a real epoch-aware system, we'd filter by epoch.
        dt = db_thresholds[0]
        
        return {
            "optimal_min": dt.optimal_min,
            "optimal_max": dt.optimal_max,
            "warn_min": dt.warn_min,
            "warn_max": dt.warn_max,
            "critical_min": dt.critical_min,
            "critical_max": dt.critical_max
        }

    def _get_static_fallback(self, parameter_name: str) -> Dict[str, Optional[float]]:
        static_obj = self._static_map.get(parameter_name)
        if not static_obj:
            return {}
            
        # Map dataclass fields to dict for consistent interface
        # Because different static classes have different field names (e.g. optimal_low vs optimal_min)
        # we try to map them dynamically or via explicit mapping.
        
        result = {
            "optimal_min": None,
            "optimal_max": None,
            "warn_min": None,
            "warn_max": None,
            "critical_min": None,
            "critical_max": None
        }
        
        if parameter_name == "PHYTOPHTHORA":
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
