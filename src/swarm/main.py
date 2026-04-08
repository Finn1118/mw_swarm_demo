from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from swarm.api.routes import knowledge, profiles, scenarios, simulations
from swarm.config import settings

app = FastAPI(
    title="MillionWays Swarm",
    description="PSI-powered multi-agent simulation engine for executive behavior prediction",
    version="0.1.0",
)

app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(simulations.router, prefix="/api/simulations", tags=["simulations"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.mount(
    "/app",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True, check_dir=False),
    name="frontend",
)


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/app/")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("swarm.main:app", host=settings.host, port=settings.port, reload=settings.debug)
