"""Registry for process-specific quality evidence providers."""

from __future__ import annotations

from src.environment.process_quality.contracts import QualityEvidenceProvider


class QualityProviderRegistry:
    """Resolve quality providers by canonical operation id."""

    def __init__(self) -> None:
        self._providers: dict[str, QualityEvidenceProvider] = {}

    def register(
        self,
        operation_id: str,
        provider: QualityEvidenceProvider,
    ) -> None:
        normalized_id = _normalize_operation_id(operation_id)
        provider_id = _normalize_operation_id(provider.operation_id)
        if provider_id != normalized_id:
            raise ValueError(
                "QUALITY_PROVIDER_OPERATION_MISMATCH:"
                f"{normalized_id}:{provider_id}"
            )
        if normalized_id in self._providers:
            raise ValueError(
                f"QUALITY_PROVIDER_ALREADY_REGISTERED:{normalized_id}"
            )
        self._providers[normalized_id] = provider

    def get(self, operation_id: str) -> QualityEvidenceProvider:
        normalized_id = _normalize_operation_id(operation_id)
        try:
            return self._providers[normalized_id]
        except KeyError as exc:
            raise KeyError(
                f"UNKNOWN_QUALITY_PROVIDER:{normalized_id}"
            ) from exc

    def operations(self) -> list[str]:
        return sorted(self._providers)


def _normalize_operation_id(operation_id: str) -> str:
    normalized_id = str(operation_id).strip().upper()
    if not normalized_id:
        raise ValueError("INVALID_QUALITY_PROVIDER_OPERATION")
    return normalized_id
