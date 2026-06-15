"""Process-specific quality evidence providers and common contracts."""

from src.environment.process_quality.contracts import (
    QualityEvidenceProvider,
    normalize_quality_evidence,
)
from src.environment.process_quality.process_a import (
    PROCESS_A_QUALITY_PROVIDER,
)
from src.environment.process_quality.process_b import (
    PROCESS_B_QUALITY_PROVIDER,
)
from src.environment.process_quality.registry import QualityProviderRegistry

QUALITY_PROVIDER_REGISTRY = QualityProviderRegistry()
QUALITY_PROVIDER_REGISTRY.register("A", PROCESS_A_QUALITY_PROVIDER)
QUALITY_PROVIDER_REGISTRY.register("B", PROCESS_B_QUALITY_PROVIDER)

__all__ = [
    "QUALITY_PROVIDER_REGISTRY",
    "QualityEvidenceProvider",
    "QualityProviderRegistry",
    "normalize_quality_evidence",
]
