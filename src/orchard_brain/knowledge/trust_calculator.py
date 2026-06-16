from database.models import TrustTier

class TrustCalculator:
    """Calculates trust scores based on TrustTier architecture."""
    
    TIER_SCORES = {
        TrustTier.TIER_1_EMPIRICAL: 1.0,
        TrustTier.TIER_2_PEER_REVIEWED: 0.8,
        TrustTier.TIER_3_EXTENSION: 0.6,
        TrustTier.TIER_4_PRIOR: 0.4
    }

    @classmethod
    def calculate_base_trust(cls, tier: TrustTier) -> float:
        """Returns the base trust score for a given tier."""
        return cls.TIER_SCORES.get(tier, 0.0)

    @classmethod
    def calculate_adjusted_trust(cls, tier: TrustTier, historical_success_rate: float) -> float:
        """Calculates an adjusted trust score incorporating historical performance."""
        base_score = cls.calculate_base_trust(tier)
        # Simple weighted adjustment for milestone 1
        return (base_score * 0.7) + (historical_success_rate * 0.3)
