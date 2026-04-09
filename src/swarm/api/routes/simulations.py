"""API routes for running simulations."""

import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from swarm import store
from swarm.knowledge.wikipedia import get_wiki_context
from swarm.output.formatter import summarize_simulation
from swarm.output.report import REPORTS_DIR
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


def _safe_report_path(filename: str) -> Path:
    if "/" in filename or "\\" in filename or not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Invalid report filename")
    report_path = (REPORTS_DIR / filename).resolve()
    reports_root = REPORTS_DIR.resolve()
    if report_path.parent != reports_root:
        raise HTTPException(status_code=400, detail="Invalid report filename")
    return report_path


def _report_metadata(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    sim_id_match = re.search(r"\*\*ID:\*\*\s*`([^`]+)`", content)
    rounds_match = re.search(r"\*\*Rounds:\*\*\s*([0-9]+)", content)
    scenario_match = re.search(r"## Scenario\s+(.+?)\s+---", content, re.DOTALL)
    scenario_preview = ""
    if scenario_match:
        scenario_preview = " ".join(scenario_match.group(1).strip().split())[:220]
    return {
        "filename": path.name,
        "path": str(path),
        "simulation_id": sim_id_match.group(1) if sim_id_match else "",
        "rounds": int(rounds_match.group(1)) if rounds_match else 0,
        "scenario_preview": scenario_preview,
        "created_at": path.stat().st_mtime,
        "size_bytes": path.stat().st_size,
    }


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


@router.get("/reports")
async def list_report_files():
    """List persisted markdown simulation reports from data/simulations."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_files = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"reports": [_report_metadata(path) for path in report_files]}


@router.get("/reports/{filename}")
async def get_report_file(filename: str):
    """Read a specific markdown simulation report."""
    report_path = _safe_report_path(filename)
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    metadata = _report_metadata(report_path)
    metadata["content"] = report_path.read_text(encoding="utf-8")
    return metadata


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    """Retrieve a past simulation by ID."""
    sim = store.simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim
