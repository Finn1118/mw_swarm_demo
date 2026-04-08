"""Action validator — checks if an agent's proposed action is consistent with their PSI profile."""

import anthropic

from swarm.config import settings


async def validate_action(
    action: str,
    psi_profile: dict,
    agent_state_summary: str,
) -> dict:
    """Validate whether a proposed action is consistent with the agent's PSI profile.

    Returns {"valid": bool, "confidence": float, "reason": str}.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = (
        "You are an expert in personality-consistent behavior assessment.\n\n"
        f"An executive with this psychological profile:\n{psi_profile.get('profile_text', '')}\n\n"
        f"Key scores: action_orientation={psi_profile.get('action_orientation', 0.5)}, "
        f"volatility={psi_profile.get('volatility', 0.5)}, "
        f"openness_to_risk={psi_profile.get('openness_to_risk', 0.5)}\n\n"
        f"Current emotional state: {agent_state_summary}\n\n"
        f"Proposed this action:\n{action}\n\n"
        "Is this action consistent with their personality profile and current state? "
        'Respond in JSON: {"valid": true/false, "confidence": 0.0-1.0, "reason": "..."}'
    )

    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    import json

    return json.loads(message.content[0].text)
