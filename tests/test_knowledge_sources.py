import pytest
from src.orchard_brain.knowledge.trust_calculator import TrustCalculator
from src.orchard_brain.knowledge.source_registry import SourceRegistry
from database.models import TrustTier, KnowledgeSourceModel

def test_trust_calculator_base_trust():
    assert TrustCalculator.calculate_base_trust(TrustTier.TIER_1_EMPIRICAL) == 1.0
    assert TrustCalculator.calculate_base_trust(TrustTier.TIER_4_PRIOR) == 0.4

def test_trust_calculator_adjusted_trust():
    # 0.8 * 0.7 + 0.9 * 0.3 = 0.56 + 0.27 = 0.83
    score = TrustCalculator.calculate_adjusted_trust(TrustTier.TIER_2_PEER_REVIEWED, 0.9)
    assert abs(score - 0.83) < 0.001

def test_source_registry():
    registry = SourceRegistry()
    
    source1 = KnowledgeSourceModel(id=1, source_name="Test 1", source_version="1.0", trust_tier=TrustTier.TIER_1_EMPIRICAL, is_active=True)
    source2 = KnowledgeSourceModel(id=2, source_name="Test 2", source_version="1.0", trust_tier=TrustTier.TIER_3_EXTENSION, is_active=False)
    
    registry.register(source1)
    registry.register(source2) # should be ignored because is_active=False
    
    assert len(registry.get_all_active()) == 1
    assert registry.get_source(1) == source1
    assert registry.get_source(2) is None
    
    registry.unregister(1)
    assert registry.get_source(1) is None
