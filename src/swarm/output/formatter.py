"""Output formatting — simulation summaries."""


def summarize_simulation(simulation_result: dict) -> dict:
    """Produce a high-level summary of a simulation run."""
    agents = simulation_result["agents"]
    rounds = simulation_result["rounds"]

    agent_summaries = {}
    for agent_name in agents:
        actions = []
        for r in rounds:
            for a in r["actions"]:
                if a["agent"] == agent_name:
                    actions.append(a["action"])
        agent_summaries[agent_name] = {
            "total_actions": len(actions),
            "last_action_snippet": actions[-1][:300] if actions else "",
        }

    return {
        "simulation_id": simulation_result["simulation_id"],
        "scenario": simulation_result["scenario"],
        "num_rounds": simulation_result["num_rounds"],
        "agent_summaries": agent_summaries,
    }
