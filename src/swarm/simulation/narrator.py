"""Narrator agent — world simulator with web search and variable time gaps.

The narrator is the bridge between agent rounds. It does NOT re-summarize the
scenario each round. Instead it:

1. Explains what each agent actually did and why it makes sense.
2. Simulates how the world reacts (markets, press, competitors, regulators).
3. Introduces exogenous developments — the world keeps moving even between
   executive moves. Uses real web search to ground these in actual industry
   dynamics, recent news, and analyst reactions.
4. Determines a realistic time gap before the next round, based on how fast
   the actions taken in this round actually play out (a tweet → hours; a major
   reorganization → weeks).
5. Tags developments per-executive with relevance (HIGH / LOW / NONE) so
   agents focus their attention realistically.

The narrator maintains cumulative state via narration_history so it never
repeats itself and the simulation feels like a continuous timeline.
"""

import json
import re

from openai import AsyncOpenAI

from swarm.config import settings


NARRATOR_INSTRUCTIONS = """\
You are the world simulator and narrator for an executive decision simulation.

You are NOT a recap engine. Do NOT re-summarize the original scenario every round.
You are simulating a living, breathing world that keeps moving between executive
moves. Each time you are called, your job is:

## 1. Explain each agent's move and the reasoning behind it
What did each executive actually decide to do this round, and why does it make
sense given their position, profile, and history? Be concrete — name names,
quote phrases, identify the strategic logic.

## 2. Simulate the world's response
When an executive acts publicly, the world reacts:
- Markets move (stock price, options activity, analyst notes)
- Press writes stories (TechCrunch, Bloomberg, FT, The Information, X/Twitter)
- Competitors respond (statements, mirror moves, silence as a signal)
- Regulators take notice (FTC, SEC, EU, state AGs)
- Customers / partners / employees react

Use the web_search tool to ground these reactions in REAL recent news about
the actual companies, executives, and sector. Search for things like:
- "[executive name] [topic] 2026"
- "[company] [recent action] reaction"
- "[sector] [event] analyst response"
Use what you find to make the world reaction realistic and specific.

## 3. Introduce exogenous developments
The world doesn't pause between rounds. Other things happen:
- A separate competitor makes a move
- A regulator drops new guidance
- An employee leaks something to The Information
- A major customer publicly comments
- A research paper drops that changes the conversation
- Macro news (rate cut, geopolitical shock, etc.)

Use web search to find ACTUAL recent news that could plausibly intrude on the
simulation timeline. Cite the source in the developments.

## 4. Determine the time gap to the next round
Different actions have different speeds. Pick the SHORTEST relevant gap based
on the FASTEST-MOVING action that triggers a meaningful response:
- "minutes"  — a tweet, an X post, a leaked Slack screenshot
- "hours"    — a press release, a media interview, an emergency all-hands
- "days"     — a customer outreach campaign, an analyst briefing tour, a product page update
- "weeks"    — a pricing change rollout, a major hire, a strategy memo to the board
- "months"   — a new product launch, an acquisition close, a major reorganization

If multiple speeds apply, use the FASTEST one — because the world will react
to the fast action and force the other executives to respond before the slow
action completes.

## 5. Tag developments per-executive with relevance
- HIGH: directly affects their company / forces a response
- LOW:  industry news they'd see but not act on
- NONE: irrelevant noise

Real executives have limited attention. Most things are LOW or NONE. Only mark
HIGH if the development specifically threatens or benefits their company, or
publicly challenges them by name.

## Output format
After you have done your research, output STRICT JSON only (no markdown, no
code fences, no commentary). The JSON must match this schema exactly:

{
  "moves_this_round": [
    {"agent": "Executive Name", "what": "1-sentence concrete description", "why": "1-sentence strategic reasoning"}
  ],
  "world_response": "1-2 paragraph description of how markets, press, competitors, regulators, customers reacted. Reference real outlets and real reactions where possible.",
  "new_developments": [
    {"description": "what intruded on the timeline", "source": "real web source if grounded, or 'inferred from sector dynamics'", "caused_by": "agent name or 'world'"}
  ],
  "time_gap": {
    "duration": "minutes|hours|days|weeks|months",
    "approximate": "e.g. '6 hours later' or '3 days later'",
    "rationale": "1-sentence explanation tied to the fastest action"
  },
  "narrative": "2-3 paragraph synthesis. This is what the executives will read at the start of the next round. Lead with the time gap, then describe what changed in the world, then frame the new pressure each executive is now facing. Do NOT recap the original scenario.",
  "per_executive": {
    "Executive Name": {
      "developments": [
        {"description": "what they specifically need to know", "relevance": "HIGH|LOW|NONE", "source_agent": "agent name or 'world'"}
      ]
    }
  }
}
"""

FINAL_ANALYSIS_INSTRUCTIONS = """\
You are the final analyst for this executive simulation.

You are no longer generating next-round narration. You are assessing the full
simulation after all rounds are complete.

Your goals:
1) Evaluate each executive's behavior against their profile
2) Identify their strongest move and biggest weakness
3) Predict what likely happens next across multiple timeframes
4) Produce a strategic assessment of winners, vulnerabilities, turning points, and risks

Output STRICT JSON only (no markdown, no code fences, no commentary) with this schema:
{
  "executive_analysis": [
    {
      "name": "Executive Name",
      "profile_alignment": "How actions did or did not match profile",
      "strongest_move": "Most consequential move and why",
      "weakness_exposed": "Blind spot, repeated mistake, or missed opportunity",
      "trajectory": "Likely direction this executive is heading"
    }
  ],
  "predictions": [
    {
      "timeframe": "1 week|1 month|3 months",
      "prediction": "What likely happens",
      "confidence": "high|medium|low",
      "basis": "Simulation evidence supporting this prediction"
    }
  ],
  "strategic_assessment": {
    "winner": "Who is in the strongest position and why",
    "most_vulnerable": "Who is most exposed and why",
    "key_turning_point": "Most consequential moment in the simulation",
    "unaddressed_risks": ["risk 1", "risk 2"]
  },
  "overall_narrative": "2-3 paragraph synthesis of what happened and what comes next"
}
"""


def _build_narrator_input(
    scenario: str,
    round_actions: list[dict],
    executives: list[dict],
    narration_history: list[dict],
    round_num: int,
) -> str:
    """Build the user input for the narrator. Cumulative history is included
    so the narrator can maintain a continuous timeline without repeating itself."""
    parts = []

    parts.append(f"# Simulation timeline — preparing the bridge into Round {round_num}\n")

    parts.append("## Original scenario (for reference only — DO NOT recap)")
    parts.append(scenario)
    parts.append("")

    parts.append("## Executives in this simulation")
    parts.append(json.dumps(
        [{"name": e["name"], "company": e["company"], "sector": e.get("sector", "")} for e in executives],
        indent=2,
    ))
    parts.append("")

    if narration_history:
        parts.append("## Prior narrations (cumulative timeline so far)")
        parts.append(
            "These are what already happened in previous rounds. Do NOT repeat any of "
            "this. Build forward from the most recent state."
        )
        for i, prior in enumerate(narration_history, start=1):
            if not prior:
                continue
            tg = prior.get("time_gap", {})
            tg_str = f"[{tg.get('approximate', '')}] " if tg else ""
            parts.append(f"\n### Bridge into Round {i + 1}")
            parts.append(f"{tg_str}{prior.get('narrative', '')}")
            new_devs = prior.get("new_developments", [])
            if new_devs:
                parts.append("**New developments that intruded:**")
                for d in new_devs:
                    parts.append(f"- {d.get('description', '')} (caused by {d.get('caused_by', 'world')})")
        parts.append("")

    parts.append("## Actions taken in the round that just finished")
    for a in round_actions:
        parts.append(f"\n### {a['agent']} ({a['company']})")
        parts.append(a["action"])
    parts.append("")

    parts.append(
        "## Your task\n"
        "Use the web_search tool to research recent real-world context about these "
        "executives, companies, and sector. Then simulate what happens next: explain "
        "the moves, simulate the world response, introduce exogenous developments, "
        "set a realistic time gap, and tag per-executive relevance. Output strict JSON only."
    )

    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the narrator's output text. Tolerates code fences
    and stray prose around the JSON block."""
    if not text:
        raise ValueError("narrator returned empty output")

    # Strip code fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # Find the first { ... last } span
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"narrator output had no JSON object: {text[:200]}")
    return json.loads(text[start : end + 1])


async def narrate_round(
    scenario: str,
    round_actions: list[dict],
    executives: list[dict],
    narration_history: list[dict] | None = None,
    round_num: int = 2,
) -> dict:
    """Generate a world-simulator narration for the bridge between rounds.

    Uses a flagship model with the web_search tool to ground the world response
    in real recent news about the executives and sector. Returns structured
    output including a time_gap field that the engine uses to inform the next
    round prompt.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    history = narration_history or []

    user_input = _build_narrator_input(
        scenario=scenario,
        round_actions=round_actions,
        executives=executives,
        narration_history=history,
        round_num=round_num,
    )

    try:
        response = await client.responses.create(
            model=settings.narrator_model,
            tools=[{"type": "web_search_preview"}],
            reasoning={"effort": settings.narrator_reasoning_effort},
            input=[
                {"role": "system", "content": NARRATOR_INSTRUCTIONS},
                {"role": "user", "content": user_input},
            ],
        )
        raw = response.output_text
        return _extract_json(raw)
    except Exception as exc:
        fallback = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.4,
            max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": NARRATOR_INSTRUCTIONS},
                {
                    "role": "user",
                    "content": user_input
                    + f"\n\n(Note: web_search unavailable in fallback mode — error: {exc}. "
                    "Make your best educated guess from training data.)",
                },
            ],
        )
        return _extract_json(fallback.choices[0].message.content)


async def generate_final_analysis(
    scenario: str,
    rounds: list[dict],
    narrations: list[dict],
    profiles: dict,
) -> dict:
    """Generate final simulation analysis and predictions."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    profile_snapshots = []
    for name, p in (profiles or {}).items():
        motives = p.get("motives", {})
        profile_snapshots.append({
            "name": name,
            "company": p.get("company", ""),
            "sector": p.get("sector", ""),
            "motives": {
                "power": motives.get("power", 0),
                "achievement": motives.get("achievement", 0),
                "contact": motives.get("contact", 0),
            },
        })

    user_input = (
        "# Final simulation analysis request\n\n"
        "## Scenario\n"
        f"{scenario}\n\n"
        "## Executive profile snapshots\n"
        f"{json.dumps(profile_snapshots, indent=2)}\n\n"
        "## Rounds and actions\n"
        f"{json.dumps(rounds, indent=2)}\n\n"
        "## Narrator bridges\n"
        f"{json.dumps(narrations, indent=2)}\n\n"
        "Use this complete history to produce the final analysis JSON."
    )

    try:
        response = await client.responses.create(
            model=settings.narrator_model,
            tools=[{"type": "web_search_preview"}],
            reasoning={"effort": settings.narrator_reasoning_effort},
            input=[
                {"role": "system", "content": FINAL_ANALYSIS_INSTRUCTIONS},
                {"role": "user", "content": user_input},
            ],
        )
        return _extract_json(response.output_text)
    except Exception as exc:
        fallback = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.4,
            max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": FINAL_ANALYSIS_INSTRUCTIONS},
                {
                    "role": "user",
                    "content": user_input
                    + f"\n\n(Note: web_search unavailable in fallback mode — error: {exc}. "
                    "Use best-available reasoning from provided simulation history.)",
                },
            ],
        )
        return _extract_json(fallback.choices[0].message.content)
