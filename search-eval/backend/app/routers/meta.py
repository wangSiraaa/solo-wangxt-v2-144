from fastapi import APIRouter

from .. import metrics

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/metric-policy")
def metric_policy():
    """The exact evaluation policy every run is scored under."""
    return metrics.POLICY_DESCRIPTION
