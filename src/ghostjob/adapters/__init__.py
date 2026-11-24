"""ATS adapter registry."""

from ghostjob.adapters.base import ATSAdapter
from ghostjob.adapters.greenhouse import GreenhouseAdapter
from ghostjob.adapters.lever import LeverAdapter
from ghostjob.adapters.ashby import AshbyAdapter
from ghostjob.core.models import ATSType

ADAPTER_REGISTRY: dict[ATSType, ATSAdapter] = {
    ATSType.GREENHOUSE: GreenhouseAdapter(),
    ATSType.LEVER: LeverAdapter(),
    ATSType.ASHBY: AshbyAdapter(),
}


def get_adapter(ats_type: ATSType | str) -> ATSAdapter | None:
    """Retrieve registered adapter for given ATS type."""
    if isinstance(ats_type, str):
        try:
            ats_type = ATSType(ats_type.lower())
        except ValueError:
            return None
    return ADAPTER_REGISTRY.get(ats_type)


__all__ = [
    "ATSAdapter",
    "GreenhouseAdapter",
    "LeverAdapter",
    "AshbyAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
]
