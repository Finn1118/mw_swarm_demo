"""API routes for running simulations."""

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from swarm import store
from swarm.knowledge.wikipedia import get_wiki_context
from swarm.output.formatter import summarize_simulation
from swarm.simulation.agent import SimAgent
from swarm.simulation.engine import run_simulation, run_simulation_stream

router = APIRouter()


class SimulationRequest(BaseModel):
    scenario: str
    executives: list[str]
    num_rounds: int = 3


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"


async def _build_agents_for_request(req: SimulationRequest) -> tuple[list[SimAgent], dict]:
    missing = [name for name in req.executives if name not in store.profiles]
    if missing:
        available = list(store.profiles.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Missing profiles for: {missing}. Available: {available}. "
            "Load samples first via POST /api/profiles/load-samples",
        )

    wiki_tasks = [get_wiki_context(name) for name in req.executives]
    wiki_results = await asyncio.gather(*wiki_tasks, return_exceptions=True)
    wiki_contexts = {}
    for name, result in zip(req.executives, wiki_results):
        if isinstance(result, Exception):
            wiki_contexts[name] = None
        else:
            wiki_contexts[name] = result

    all_names = req.executives
    agents = []
    for name in req.executives:
        profile = store.profiles[name]
        knowledge = store.graph.get_context_for_executive(name)
        if not any(knowledge.values()):
            knowledge = store.knowledge.get(
                name, {"decisions": [], "companies": [], "events": [], "relationships": []}
            )

        other_names = [n for n in all_names if n != name]
        agents.append(
            SimAgent(
                name=name,
                title=profile.get("title", "Executive"),
                company=profile.get("company", "Unknown"),
                sector=profile.get("sector", ""),
                profile=profile,
                knowledge_context=knowledge,
                wiki_context=wiki_contexts.get(name),
                other_agents=other_names,
            )
        )

    sim_profiles = {name: store.profiles[name] for name in req.executives}
    return agents, sim_profiles


@router.post("/run")
async def run_sim(req: SimulationRequest):
    """Run a multi-agent simulation with narrator-mediated interaction."""
    agents, sim_profiles = await _build_agents_for_request(req)

    result = await run_simulation(
        agents=agents,
        scenario=req.scenario,
        num_rounds=req.num_rounds,
        profiles=sim_profiles,
    )

    store.simulations[result["simulation_id"]] = result
    summary = summarize_simulation(result)

    return {
        "summary": summary,
        "report_path": result.get("report_path", ""),
        "full_log": result,
    }


@router.post("/run/stream")
async def run_sim_stream(req: SimulationRequest):
    """Run a simulation and stream step-by-step events as SSE."""
    agents, sim_profiles = await _build_agents_for_request(req)

    async def event_generator():
        async for event in run_simulation_stream(
            agents=agents,
            scenario=req.scenario,
            num_rounds=req.num_rounds,
            profiles=sim_profiles,
        ):
            event_type = event.get("event", "message")
            data = event.get("data", {})

            if event_type == "complete":
                result = data.get("result")
                if result:
                    store.simulations[result["simulation_id"]] = result
                    payload = {
                        "summary": summarize_simulation(result),
                        "report_path": result.get("report_path", ""),
                        "full_log": result,
                    }
                    yield _sse_event("complete", payload)
                    continue

            yield _sse_event(event_type, data)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/")
async def list_simulations():
    """List all stored simulations."""
    return {
        sid: {
            "scenario": sim["scenario"][:100],
            "agents": sim["agents"],
            "num_rounds": sim["num_rounds"],
            "report_path": sim.get("report_path", ""),
        }
        for sid, sim in store.simulations.items()
    }


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    """Retrieve a past simulation by ID."""
    sim = store.simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim
