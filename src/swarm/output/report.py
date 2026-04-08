"""Markdown simulation report generator."""

import os
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("E:/millionways_swarm/data/simulations")


def _extract_motives_emotions(profile: dict) -> tuple[dict, dict]:
    """Extract motives and emotions from either profile format."""
    if profile.get("object") == "analysis":
        # API v2 format
        motives = profile.get("motives", {})
        affect = profile.get("affect", {})
        return (
            {"power": motives.get("power", 0), "achievement": motives.get("achievement", 0), "contact": motives.get("contact", 0)},
            {"approach": affect.get("approach", 50), "avoidance": affect.get("avoidance", 50)},
        )
    # Old sample format
    result = profile.get("result", {})
    return result.get("motives", {}), result.get("emotions", {})


def generate_report(simulation_result: dict, narrations: list[dict], profiles: dict) -> str:
    """Generate a full markdown report of a simulation run."""
    sim_id = simulation_result["simulation_id"]
    scenario = simulation_result["scenario"]
    agents = simulation_result["agents"]
    rounds = simulation_result["rounds"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# Simulation Report",
        f"**ID:** `{sim_id}`",
        f"**Date:** {timestamp}",
        f"**Rounds:** {simulation_result['num_rounds']}",
        "",
        "---",
        "",
        "## Scenario",
        scenario,
        "",
        "---",
        "",
        "## Executive Profiles",
    ]

    for agent_name in agents:
        profile = profiles.get(agent_name, {})
        motives, emotions = _extract_motives_emotions(profile)
        lines.extend([
            f"### {agent_name} — {profile.get('title', '')} of {profile.get('company', '')}",
            f"- **Motives:** Power {motives.get('power', 0):.0f}% | "
            f"Achievement {motives.get('achievement', 0):.0f}% | "
            f"Contact {motives.get('contact', 0):.0f}%",
            f"- **Emotional Style:** Approach {emotions.get('approach', 50)}% | "
            f"Avoidance {emotions.get('avoidance', 50)}%",
            "",
        ])

    lines.extend(["---", "", "## Simulation Rounds", ""])

    for i, round_data in enumerate(rounds):
        round_num = round_data["round"]

        # Narrator block (the bridge into this round)
        if i < len(narrations) and narrations[i]:
            narration = narrations[i]
            time_gap = narration.get("time_gap", {}) or {}
            approx = time_gap.get("approximate", "")
            header = f"### Round {round_num}" + (f" — {approx}" if approx else "")
            lines.append(header)
            lines.append("")

            if time_gap.get("rationale"):
                lines.extend([f"_Time elapsed: {time_gap['rationale']}_", ""])

            narrative = narration.get("narrative", "")
            if narrative:
                lines.extend([f"**Narrator:** {narrative}", ""])

            world_response = narration.get("world_response", "")
            if world_response:
                lines.extend(["**World response:**", world_response, ""])

            new_devs = narration.get("new_developments", []) or []
            if new_devs:
                lines.append("**New developments:**")
                for d in new_devs:
                    desc = d.get("description", "")
                    src = d.get("source", "")
                    caused = d.get("caused_by", "")
                    suffix_parts = []
                    if caused:
                        suffix_parts.append(f"caused by {caused}")
                    if src:
                        suffix_parts.append(f"source: {src}")
                    suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
                    lines.append(f"- {desc}{suffix}")
                lines.append("")
        else:
            lines.append(f"### Round {round_num}")
            lines.append("")

        for action in round_data["actions"]:
            lines.extend([
                f"#### {action['agent']} ({action['company']})",
                "",
                action["action"],
                "",
            ])

        lines.extend(["---", ""])

    final_analysis = simulation_result.get("final_analysis") or {}
    if final_analysis:
        lines.extend(["## Final Analysis", ""])

        exec_analysis = final_analysis.get("executive_analysis", []) or []
        if exec_analysis:
            lines.extend(["### Executive Analysis", ""])
            for entry in exec_analysis:
                lines.extend([
                    f"#### {entry.get('name', 'Executive')}",
                    f"- **Profile alignment:** {entry.get('profile_alignment', '')}",
                    f"- **Strongest move:** {entry.get('strongest_move', '')}",
                    f"- **Weakness exposed:** {entry.get('weakness_exposed', '')}",
                    f"- **Trajectory:** {entry.get('trajectory', '')}",
                    "",
                ])

        predictions = final_analysis.get("predictions", []) or []
        if predictions:
            lines.extend(["### Predictions", ""])
            for p in predictions:
                lines.extend([
                    f"- **{p.get('timeframe', 'Future')}** — {p.get('prediction', '')}",
                    f"  - Confidence: {p.get('confidence', '')}",
                    f"  - Basis: {p.get('basis', '')}",
                ])
            lines.append("")

        strategic = final_analysis.get("strategic_assessment", {}) or {}
        if strategic:
            lines.extend([
                "### Strategic Assessment",
                f"- **Winner:** {strategic.get('winner', '')}",
                f"- **Most vulnerable:** {strategic.get('most_vulnerable', '')}",
                f"- **Key turning point:** {strategic.get('key_turning_point', '')}",
            ])
            risks = strategic.get("unaddressed_risks", []) or []
            if risks:
                lines.append("- **Unaddressed risks:**")
                for risk in risks:
                    lines.append(f"  - {risk}")
            lines.append("")

        if final_analysis.get("overall_narrative"):
            lines.extend([
                "### Overall Narrative",
                final_analysis.get("overall_narrative", ""),
                "",
            ])
    else:
        # Fallback summary if final analysis is unavailable
        lines.extend([
            "## Summary",
            "",
            "| Executive | Company | Actions Taken |",
            "|---|---|---|",
        ])
        for agent_name in agents:
            profile = profiles.get(agent_name, {})
            action_count = sum(1 for r in rounds for a in r["actions"] if a["agent"] == agent_name)
            lines.append(f"| {agent_name} | {profile.get('company', '')} | {action_count} |")

    return "\n".join(lines)


def save_report(simulation_result: dict, narrations: list[dict], profiles: dict) -> str:
    """Generate and save a markdown report. Returns the file path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sim_id = simulation_result["simulation_id"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{sim_id[:8]}.md"
    filepath = REPORTS_DIR / filename

    report = generate_report(simulation_result, narrations, profiles)
    filepath.write_text(report, encoding="utf-8")

    return str(filepath)
