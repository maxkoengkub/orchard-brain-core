import pytest
from unittest.mock import AsyncMock, MagicMock
from src.orchard_brain.knowledge.evidence_engine import EvidenceEngine
from src.orchard_brain.knowledge.source_registry import SourceRegistry
from database.evidence_repository import EvidenceRepository
from database.models import KnowledgeSourceModel, TrustTier, RiskEvidenceModel

@pytest.mark.asyncio
async def test_record_risk_evidence_success():
    mock_repo = AsyncMock(spec=EvidenceRepository)
    mock_registry = MagicMock(spec=SourceRegistry)
    
    source = KnowledgeSourceModel(id=1, is_active=True)
    mock_registry.get_source.return_value = source
    
    engine = EvidenceEngine(repository=mock_repo, registry=mock_registry)
    
    await engine.record_risk_evidence(
        risk_id=100,
        source_id=1,
        rule_key="high_temp_risk",
        rule_version="1.0",
        confidence_weight=0.9
    )
    
    mock_repo.add_risk_evidence.assert_called_once()
    args = mock_repo.add_risk_evidence.call_args[1]
    assert args["risk_id"] == 100
    assert args["source_id"] == 1
    assert args["rule_key"] == "high_temp_risk"
    assert args["rule_version"] == "1.0"

@pytest.mark.asyncio
async def test_record_risk_evidence_fails_inactive_source():
    mock_repo = AsyncMock(spec=EvidenceRepository)
    mock_registry = MagicMock(spec=SourceRegistry)
    
    mock_registry.get_source.return_value = None
    
    engine = EvidenceEngine(repository=mock_repo, registry=mock_registry)
    
    with pytest.raises(ValueError, match="is not an active knowledge source"):
        await engine.record_risk_evidence(
            risk_id=100,
            source_id=999,
            rule_key="high_temp_risk",
            rule_version="1.0",
            confidence_weight=0.9
        )
    
    mock_repo.add_risk_evidence.assert_not_called()
