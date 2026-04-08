"""API routes for scenario definition and executive resolution."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ScenarioRequest(BaseModel):
    description: str
    industry: str | None = None
    companies: list[str] | None = None


class ResolvedScenario(BaseModel):
    description: str
    resolved_companies: list[str]
    resolved_executives: list[dict]


@router.post("/resolve", response_model=ResolvedScenario)
async def resolve_scenario(req: ScenarioRequest):
    """Auto-resolve which executives and companies are relevant to a scenario.

    TODO: Use LLM + company/industry index to resolve relevant actors.
    """
    # Placeholder — returns the explicitly listed companies or empty
    return ResolvedScenario(
        description=req.description,
        resolved_companies=req.companies or [],
        resolved_executives=[],
    )
