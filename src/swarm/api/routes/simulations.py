"""API routes for running simulations."""

import asyncio
import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


class ReplayRequest(BaseModel):
    delay_seconds: float = Field(default=3.0, ge=0.2, le=120.0)


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


def _extract_between(content: str, start_header: str, end_headers: tuple[str, ...]) -> str:
    start = content.find(start_header)
    if start < 0:
        return ""
    start += len(start_header)
    end = len(content)
    for marker in end_headers:
        idx = content.find(marker, start)
        if idx >= 0:
            end = min(end, idx)
    return content[start:end].strip()


def _parse_profiles_from_report(content: str) -> dict[str, dict]:
    section = _extract_between(content, "## Executive Profiles", ("## Simulation Rounds", "## Final Analysis", "## Summary"))
    profiles: dict[str, dict] = {}
    current_name = None
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            header = line[4:]
            match = re.match(r"(.+?)\s+—\s+(.+?)\s+of\s+(.+)", header)
            if match:
                name, title, company = match.groups()
            else:
                name, title, company = header, "Executive", "Unknown"
            current_name = name.strip()
            profiles[current_name] = {
                "name": current_name,
                "title": title.strip(),
                "company": company.strip(),
                "sector": "",
                "motives": {"power": 0, "achievement": 0, "contact": 0},
                "emotions": {"approach": 50, "avoidance": 50},
            }
            continue
        if not current_name:
            continue
        motives_match = re.search(
            r"Power\s+([0-9.]+)%\s+\|\s+Achievement\s+([0-9.]+)%\s+\|\s+Contact\s+([0-9.]+)%",
            line,
        )
        if motives_match:
            power, achievement, contact = motives_match.groups()
            profiles[current_name]["motives"] = {
                "power": float(power),
                "achievement": float(achievement),
                "contact": float(contact),
            }
            continue
        emotions_match = re.search(
            r"Approach\s+([0-9.]+)%\s+\|\s+Avoidance\s+([0-9.]+)%",
            line,
        )
        if emotions_match:
            approach, avoidance = emotions_match.groups()
            profiles[current_name]["emotions"] = {
                "approach": float(approach),
                "avoidance": float(avoidance),
            }
    return profiles


def _parse_rounds_from_report(content: str) -> tuple[list[dict], list[dict | None]]:
    section = _extract_between(content, "## Simulation Rounds", ("## Final Analysis", "## Summary"))
    lines = section.splitlines()
    rounds: list[dict] = []
    narrations: list[dict | None] = []
    current_round = None
    actions: list[dict] = []
    narration: dict | None = None
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        round_match = re.match(r"###\s+Round\s+([0-9]+)(?:\s+—\s+(.+))?", stripped)
        if round_match:
            if current_round is not None:
                rounds.append({"round": current_round, "actions": actions})
                narrations.append(narration)
            current_round = int(round_match.group(1))
            approx = (round_match.group(2) or "").strip()
            actions = []
            narration = None
            if approx:
                narration = {
                    "time_gap": {"approximate": approx, "rationale": ""},
                    "narrative": "",
                    "world_response": "",
                    "new_developments": [],
                }
            i += 1
            continue

        if current_round is None:
            i += 1
            continue

        if stripped.startswith("_Time elapsed:") and stripped.endswith("_"):
            value = stripped[len("_Time elapsed:") : -1].strip()
            narration = narration or {"time_gap": {}, "narrative": "", "world_response": "", "new_developments": []}
            narration.setdefault("time_gap", {})
            narration["time_gap"]["rationale"] = value
            i += 1
            continue

        if stripped.startswith("**Narrator:**"):
            text = stripped[len("**Narrator:**") :].strip()
            narration = narration or {"time_gap": {}, "narrative": "", "world_response": "", "new_developments": []}
            narration["narrative"] = text
            i += 1
            continue

        if stripped == "**World response:**":
            i += 1
            buffer = []
            while i < len(lines):
                peek = lines[i].strip()
                if not peek:
                    if buffer:
                        buffer.append("")
                    i += 1
                    continue
                if peek.startswith("**New developments:**") or peek.startswith("#### ") or peek.startswith("### ") or peek == "---":
                    break
                buffer.append(lines[i].rstrip())
                i += 1
            narration = narration or {"time_gap": {}, "narrative": "", "world_response": "", "new_developments": []}
            narration["world_response"] = "\n".join(buffer).strip()
            continue

        if stripped == "**New developments:**":
            i += 1
            new_devs = []
            while i < len(lines):
                peek = lines[i].strip()
                if peek.startswith("- "):
                    text = peek[2:].strip()
                    source_match = re.search(r"source:\s*(https?://[^\s)]+)", text)
                    source = source_match.group(1) if source_match else ""
                    clean_text = re.sub(r"\s*\(caused by .+\)\s*$", "", text).strip()
                    caused_match = re.search(r"\(caused by ([^)]+)\)", text)
                    caused_by = caused_match.group(1).strip() if caused_match else "world"
                    new_devs.append({"description": clean_text, "source": source, "caused_by": caused_by})
                    i += 1
                    continue
                if not peek:
                    i += 1
                    continue
                break
            narration = narration or {"time_gap": {}, "narrative": "", "world_response": "", "new_developments": []}
            narration["new_developments"] = new_devs
            continue

        action_match = re.match(r"####\s+(.+?)\s+\((.+?)\)", stripped)
        if action_match:
            agent, company = action_match.groups()
            i += 1
            body: list[str] = []
            while i < len(lines):
                peek = lines[i].strip()
                if peek.startswith("#### ") or peek.startswith("### ") or peek == "---":
                    break
                body.append(lines[i].rstrip())
                i += 1
            action_text = "\n".join(body).strip()
            actions.append({"agent": agent.strip(), "company": company.strip(), "action": action_text})
            continue

        i += 1

    if current_round is not None:
        rounds.append({"round": current_round, "actions": actions})
        narrations.append(narration)

    return rounds, narrations


def _parse_final_analysis_from_report(content: str) -> dict:
    section = _extract_between(content, "## Final Analysis", ())
    if not section:
        return {}

    executive_analysis: list[dict] = []
    predictions: list[dict] = []
    strategic_assessment = {
        "winner": "",
        "most_vulnerable": "",
        "key_turning_point": "",
        "unaddressed_risks": [],
    }

    exec_block = _extract_between(section, "### Executive Analysis", ("### Predictions", "### Strategic Assessment", "### Overall Narrative"))
    for chunk in re.split(r"\n(?=####\s+)", exec_block):
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines or not lines[0].startswith("#### "):
            continue
        entry = {
            "name": lines[0][5:].strip(),
            "profile_alignment": "",
            "strongest_move": "",
            "weakness_exposed": "",
            "trajectory": "",
        }
        for ln in lines[1:]:
            if ln.startswith("- **Profile alignment:**"):
                entry["profile_alignment"] = ln.split(":", 1)[1].strip()
            elif ln.startswith("- **Strongest move:**"):
                entry["strongest_move"] = ln.split(":", 1)[1].strip()
            elif ln.startswith("- **Weakness exposed:**"):
                entry["weakness_exposed"] = ln.split(":", 1)[1].strip()
            elif ln.startswith("- **Trajectory:**"):
                entry["trajectory"] = ln.split(":", 1)[1].strip()
        executive_analysis.append(entry)

    pred_block = _extract_between(section, "### Predictions", ("### Strategic Assessment", "### Overall Narrative"))
    current_prediction = None
    for ln in pred_block.splitlines():
        stripped = ln.strip()
        if not stripped:
            continue
        start_match = re.match(r"-\s+\*\*(.+?)\*\*\s+—\s+(.+)", stripped)
        if start_match:
            if current_prediction:
                predictions.append(current_prediction)
            timeframe, prediction = start_match.groups()
            current_prediction = {
                "timeframe": timeframe.strip(),
                "prediction": prediction.strip(),
                "confidence": "",
                "basis": "",
            }
            continue
        if current_prediction and stripped.startswith("- Confidence:"):
            current_prediction["confidence"] = stripped.split(":", 1)[1].strip()
            continue
        if current_prediction and stripped.startswith("- Basis:"):
            current_prediction["basis"] = stripped.split(":", 1)[1].strip()
            continue
    if current_prediction:
        predictions.append(current_prediction)

    strat_block = _extract_between(section, "### Strategic Assessment", ("### Overall Narrative",))
    parsing_risks = False
    for ln in strat_block.splitlines():
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("- **Winner:**"):
            strategic_assessment["winner"] = stripped.split(":", 1)[1].strip()
            parsing_risks = False
            continue
        if stripped.startswith("- **Most vulnerable:**"):
            strategic_assessment["most_vulnerable"] = stripped.split(":", 1)[1].strip()
            parsing_risks = False
            continue
        if stripped.startswith("- **Key turning point:**"):
            strategic_assessment["key_turning_point"] = stripped.split(":", 1)[1].strip()
            parsing_risks = False
            continue
        if stripped.startswith("- **Unaddressed risks:**"):
            parsing_risks = True
            continue
        if parsing_risks and stripped.startswith("- "):
            strategic_assessment["unaddressed_risks"].append(stripped[2:].strip())

    overall_narrative = _extract_between(section, "### Overall Narrative", ())

    return {
        "executive_analysis": executive_analysis,
        "predictions": predictions,
        "strategic_assessment": strategic_assessment,
        "overall_narrative": overall_narrative.strip(),
    }


def _parse_report_for_replay(report_path: Path) -> dict:
    content = report_path.read_text(encoding="utf-8")
    metadata = _report_metadata(report_path)
    scenario_match = re.search(r"## Scenario\s+(.+?)\s+---", content, re.DOTALL)
    scenario_text = " ".join((scenario_match.group(1).strip() if scenario_match else "").split())
    profiles = _parse_profiles_from_report(content)
    rounds, narrations = _parse_rounds_from_report(content)
    final_analysis = _parse_final_analysis_from_report(content)

    agents = list(profiles.keys())
    if not agents:
        seen = []
        for round_data in rounds:
            for action in round_data.get("actions", []):
                name = action.get("agent", "")
                if name and name not in seen:
                    seen.append(name)
        agents = seen
        profiles = {
            name: {
                "name": name,
                "title": "Executive",
                "company": "Unknown",
                "sector": "",
                "motives": {"power": 0, "achievement": 0, "contact": 0},
                "emotions": {"approach": 50, "avoidance": 50},
            }
            for name in agents
        }

    return {
        "simulation_id": metadata.get("simulation_id") or report_path.stem,
        "scenario": scenario_text or metadata.get("scenario_preview") or "Replay from saved simulation report",
        "agents": agents,
        "num_rounds": len(rounds),
        "rounds": rounds,
        "narrations": narrations,
        "profiles": profiles,
        "final_analysis": final_analysis,
        "report_path": str(report_path),
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


@router.post("/reports/{filename}/replay/stream")
async def replay_report_stream(filename: str, req: ReplayRequest):
    """Replay a stored markdown simulation report as SSE events (no model/API calls)."""
    report_path = _safe_report_path(filename)
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    parsed = _parse_report_for_replay(report_path)
    base_id = parsed.get("simulation_id") or report_path.stem
    replay_id = f"replay-{base_id}-{uuid.uuid4().hex[:8]}"
    delay = float(req.delay_seconds)

    async def event_generator():
        replay_result = {
            "simulation_id": replay_id,
            "scenario": parsed["scenario"],
            "agents": parsed["agents"],
            "num_rounds": parsed["num_rounds"],
            "rounds": parsed["rounds"],
            "narrations": parsed["narrations"],
            "profiles": parsed["profiles"],
            "final_analysis": parsed.get("final_analysis") or {},
            "report_path": parsed["report_path"],
        }

        yield _sse_event(
            "init",
            {
                "simulation_id": replay_id,
                "scenario": replay_result["scenario"],
                "agents": replay_result["agents"],
                "num_rounds": replay_result["num_rounds"],
                "profiles": replay_result["profiles"],
            },
        )

        for idx, round_data in enumerate(replay_result["rounds"], start=1):
            round_num = round_data.get("round", idx)
            yield _sse_event("round_start", {"round": round_num})
            await asyncio.sleep(delay)

            narration = None
            if idx - 1 < len(replay_result["narrations"]):
                narration = replay_result["narrations"][idx - 1]
            if narration:
                yield _sse_event("narration", {"round": round_num, "narration": narration})
                await asyncio.sleep(delay)

            for action in round_data.get("actions", []):
                agent_name = action.get("agent", "")
                yield _sse_event("agent_thinking", {"round": round_num, "agent": agent_name})
                await asyncio.sleep(min(1.5, max(0.2, delay / 3)))
                yield _sse_event(
                    "agent_action",
                    {
                        "round": round_num,
                        "agent": agent_name,
                        "company": action.get("company", ""),
                        "action": action.get("action", ""),
                    },
                )
                await asyncio.sleep(delay)

        final_analysis = replay_result.get("final_analysis") or {}
        if final_analysis:
            yield _sse_event("final_analysis", final_analysis)
            await asyncio.sleep(min(1.5, delay))

        store.simulations[replay_id] = replay_result
        payload = {
            "summary": summarize_simulation(replay_result),
            "report_path": replay_result["report_path"],
            "full_log": replay_result,
        }
        yield _sse_event("complete", payload)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    """Retrieve a past simulation by ID."""
    sim = store.simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim
