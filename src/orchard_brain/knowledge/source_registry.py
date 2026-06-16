from typing import Dict, List, Optional
from database.models import KnowledgeSourceModel, TrustTier

class SourceRegistry:
    """In-memory registry for active knowledge sources."""
    
    def __init__(self):
        self._sources: Dict[int, KnowledgeSourceModel] = {}

    def register(self, source: KnowledgeSourceModel) -> None:
        """Registers a knowledge source if it is active."""
        if source.is_active:
            self._sources[source.id] = source

    def unregister(self, source_id: int) -> None:
        """Removes a knowledge source from the registry."""
        self._sources.pop(source_id, None)

    def get_source(self, source_id: int) -> Optional[KnowledgeSourceModel]:
        """Retrieves a source by its ID."""
        return self._sources.get(source_id)

    def get_all_active(self) -> List[KnowledgeSourceModel]:
        """Returns all registered active knowledge sources."""
        return list(self._sources.values())
    
    def get_by_tier(self, tier: TrustTier) -> List[KnowledgeSourceModel]:
        """Returns sources matching a specific trust tier."""
        return [s for s in self._sources.values() if s.trust_tier == tier]
