"""Multi-agent simulation engine with narrator and relevance tagging."""

import uuid

from openai import AsyncOpenAI

from swarm.config import settings
from swarm.output.report import save_report
from swarm.simulation.agent import SimAgent
from swarm.simulation.narrator import generate_final_analysis, narrate_round


def _extract_motives_emotions(profile: dict) -> tuple[dict, dict]:
    """Extract motives and emotions from either profile format."""
    if profile.get("object") == "analysis":
        motives = profile.get("motives", {})
        affect = profile.get("affect", {})
        return (
            {
                "power": motives.get("power", 0),
                "achievement": motives.get("achievement", 0),
                "contact": motives.get("contact", 0),
            },
            {
                "approach": affect.get("approach", 50),
                "avoidance": affect.get("avoidance", 50),
            },
        )

    result = profile.get("result", {})
    return result.get("motives", {}), result.get("emotions", {})


def _build_profiles_summary(agents: list[SimAgent], profiles: dict | None) -> dict[str, dict]:
    """Build a compact profile summary for frontend rendering."""
    provided_profiles = profiles or {}
    summary: dict[str, dict] = {}

    for agent in agents:
        profile = provided_profiles.get(agent.name, agent.profile)
        motives, emotions = _extract_motives_emotions(profile)
        summary[agent.name] = {
            "name": agent.name,
            "title": agent.title,
            "company": agent.company,
            "sector": agent.sector,
            "motives": motives,
            "emotions": emotions,
        }

    return summary


def _compact_summary(text: str, max_len: int = 160) -> str:
    """Build a short one-line summary from model output."""
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""
    end_idx = cleaned.find(". ")
    if 0 < end_idx < max_len:
        return cleaned[: end_idx + 1]
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + "..."


async def run_simulation(
    agents: list[SimAgent],
    scenario: str,
    num_rounds: int | None = None,
    profiles: dict | None = None,
) -> dict:
    """Run a multi-round simulation with narrator-mediated interaction."""
    num_rounds = num_rounds or settings.sim_max_rounds
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    simulation_id = str(uuid.uuid4())

    rounds = []
    narrations = []
    executives_meta = [
        {"name": a.name, "company": a.company, "sector": a.sector} for a in agents
    ]

    for round_num in range(1, num_rounds + 1):
        round_actions = []

        if round_num == 1:
            # First round: everyone responds to the raw scenario
            for agent in agents:
                user_prompt = (
                    f"## Round 1 — Initial Scenario\n{scenario}\n\n"
                    "This situation just broke. What is your immediate response?\n"
                    "Respond as your personality demands. You may take bold action, wait and observe, "
                    "or do nothing if the situation does not concern you. "
                    "You may directly reference other executives by name. "
                    "Remember: this is an ongoing situation — don't try to solve everything now. "
                    "Consider what you want to set in motion for the rounds ahead."
                )
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    max_tokens=1024,
                    temperature=settings.sim_temperature,
                    messages=[
                        {"role": "system", "content": agent.build_system_prompt()},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                action_text = response.choices[0].message.content
                round_actions.append({
                    "agent": agent.name,
                    "company": agent.company,
                    "action": action_text,
                })
                agent.actions_taken.append(
                    {"round": round_num, "action": action_text, "summary": _compact_summary(action_text)}
                )

            narrations.append(None)  # no narration before round 1
        else:
            # Subsequent rounds: narrator synthesizes, then agents respond to tagged developments.
            # Pass the full cumulative narration history so the narrator never repeats itself.
            prev_actions = rounds[-1]["actions"]
            prior_narrations = [n for n in narrations if n]
            narration = await narrate_round(
                scenario=scenario,
                round_actions=prev_actions,
                executives=executives_meta,
                narration_history=prior_narrations,
                round_num=round_num,
            )
            narrations.append(narration)

            narrative = narration.get("narrative", "")
            per_exec = narration.get("per_executive", {})
            time_gap = narration.get("time_gap", {})

            for agent in agents:
                agent_devs = per_exec.get(agent.name, {}).get("developments", [])
                other_exec_actions = [
                    {
                        "agent": a.get("agent", ""),
                        "company": a.get("company", ""),
                        "summary": _compact_summary(a.get("action", "")),
                    }
                    for a in prev_actions
                    if a.get("agent") != agent.name
                ]
                user_prompt = agent.build_round_prompt(
                    round_num,
                    agent_devs,
                    narrative,
                    time_gap=time_gap,
                    own_action_history=agent.actions_taken,
                    other_exec_actions=other_exec_actions,
                )

                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    max_tokens=1024,
                    temperature=settings.sim_temperature,
                    messages=[
                        {"role": "system", "content": agent.build_system_prompt()},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                action_text = response.choices[0].message.content
                round_actions.append({
                    "agent": agent.name,
                    "company": agent.company,
                    "action": action_text,
                })
                agent.actions_taken.append(
                    {"round": round_num, "action": action_text, "summary": _compact_summary(action_text)}
                )

        rounds.append({"round": round_num, "actions": round_actions})

    result = {
        "simulation_id": simulation_id,
        "scenario": scenario,
        "agents": [a.name for a in agents],
        "num_rounds": num_rounds,
        "rounds": rounds,
        "narrations": narrations,
        "profiles": _build_profiles_summary(agents, profiles),
    }
    result["final_analysis"] = await generate_final_analysis(
        scenario=scenario,
        rounds=rounds,
        narrations=narrations,
        profiles=result["profiles"],
    )

    # Save markdown report
    report_path = save_report(result, narrations, profiles or {})
    result["report_path"] = report_path

    return result


async def run_simulation_stream(
    agents: list[SimAgent],
    scenario: str,
    num_rounds: int | None = None,
    profiles: dict | None = None,
):
    """Run a simulation and stream step-by-step events."""
    num_rounds = num_rounds or settings.sim_max_rounds
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    simulation_id = str(uuid.uuid4())

    rounds = []
    narrations = []
    profiles_summary = _build_profiles_summary(agents, profiles)
    executives_meta = [
        {"name": a.name, "company": a.company, "sector": a.sector} for a in agents
    ]

    try:
        yield {
            "event": "init",
            "data": {
                "simulation_id": simulation_id,
                "scenario": scenario,
                "agents": [a.name for a in agents],
                "num_rounds": num_rounds,
                "profiles": profiles_summary,
            },
        }

        for round_num in range(1, num_rounds + 1):
            round_actions = []
            yield {"event": "round_start", "data": {"round": round_num}}

            if round_num == 1:
                narrations.append(None)
                narrative = ""
                per_exec = {}
                time_gap = {}
            else:
                prev_actions = rounds[-1]["actions"]
                prior_narrations = [n for n in narrations if n]
                narration = await narrate_round(
                    scenario=scenario,
                    round_actions=prev_actions,
                    executives=executives_meta,
                    narration_history=prior_narrations,
                    round_num=round_num,
                )
                narrations.append(narration)
                narrative = narration.get("narrative", "")
                per_exec = narration.get("per_executive", {})
                time_gap = narration.get("time_gap", {})

                yield {
                    "event": "narration",
                    "data": {
                        "round": round_num,
                        "narration": narration,
                    },
                }

            for agent in agents:
                yield {
                    "event": "agent_thinking",
                    "data": {"round": round_num, "agent": agent.name},
                }

                if round_num == 1:
                    user_prompt = (
                        f"## Round 1 — Initial Scenario\n{scenario}\n\n"
                        "This situation just broke. What is your immediate response?\n"
                        "Respond as your personality demands. You may take bold action, wait and observe, "
                        "or do nothing if the situation does not concern you. "
                        "You may directly reference other executives by name. "
                        "Remember: this is an ongoing situation — don't try to solve everything now. "
                        "Consider what you want to set in motion for the rounds ahead."
                    )
                else:
                    agent_devs = per_exec.get(agent.name, {}).get("developments", [])
                    other_exec_actions = [
                        {
                            "agent": a.get("agent", ""),
                            "company": a.get("company", ""),
                            "summary": _compact_summary(a.get("action", "")),
                        }
                        for a in prev_actions
                        if a.get("agent") != agent.name
                    ]
                    user_prompt = agent.build_round_prompt(
                        round_num,
                        agent_devs,
                        narrative,
                        time_gap=time_gap,
                        own_action_history=agent.actions_taken,
                        other_exec_actions=other_exec_actions,
                    )

                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    max_tokens=1024,
                    temperature=settings.sim_temperature,
                    messages=[
                        {"role": "system", "content": agent.build_system_prompt()},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                action_text = response.choices[0].message.content
                action_entry = {
                    "agent": agent.name,
                    "company": agent.company,
                    "action": action_text,
                }
                round_actions.append(action_entry)
                agent.actions_taken.append(
                    {"round": round_num, "action": action_text, "summary": _compact_summary(action_text)}
                )

                yield {
                    "event": "agent_action",
                    "data": {
                        "round": round_num,
                        "agent": agent.name,
                        "company": agent.company,
                        "action": action_text,
                    },
                }

            rounds.append({"round": round_num, "actions": round_actions})

        result = {
            "simulation_id": simulation_id,
            "scenario": scenario,
            "agents": [a.name for a in agents],
            "num_rounds": num_rounds,
            "rounds": rounds,
            "narrations": narrations,
            "profiles": profiles_summary,
        }
        result["final_analysis"] = await generate_final_analysis(
            scenario=scenario,
            rounds=rounds,
            narrations=narrations,
            profiles=profiles_summary,
        )
        yield {
            "event": "final_analysis",
            "data": result["final_analysis"],
        }

        report_path = save_report(result, narrations, profiles or {})
        result["report_path"] = report_path

        yield {
            "event": "complete",
            "data": {
                "simulation_id": simulation_id,
                "report_path": report_path,
                "result": result,
            },
        }
    except Exception as exc:
        yield {
            "event": "error",
            "data": {"message": str(exc)},
        }
