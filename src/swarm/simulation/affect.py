"""Affect dynamics — updates agent emotional state between simulation rounds."""

from swarm.simulation.agent import AgentState


def update_affect(state: AgentState, round_outcome: str, psi_profile: dict) -> AgentState:
    """Estimate the agent's new affective state after a simulation round.

    Uses PSI theory principles:
    - High self-regulation → faster recovery from negative affect
    - High volatility → larger affect swings
    - Positive outcomes → broaden-and-build (more risk tolerance, positive valence)
    - Negative outcomes → narrowing (less risk tolerance, negative valence)
    """
    volatility = psi_profile.get("volatility", 0.5)
    self_reg = psi_profile.get("self_regulation", 0.5)

    # Classify outcome sentiment (simplified — could use LLM for nuance)
    outcome_lower = round_outcome.lower()
    positive_signals = ["success", "gain", "win", "growth", "approved", "positive"]
    negative_signals = ["loss", "fail", "decline", "crisis", "reject", "negative"]

    sentiment = 0.0
    for word in positive_signals:
        if word in outcome_lower:
            sentiment += 0.2
    for word in negative_signals:
        if word in outcome_lower:
            sentiment -= 0.2
    sentiment = max(-1.0, min(1.0, sentiment))

    # Apply volatility as a multiplier on affect change
    affect_delta = sentiment * (0.5 + volatility * 0.5)

    # Self-regulation dampens negative shifts
    if affect_delta < 0:
        affect_delta *= 1.0 - (self_reg * 0.5)

    new_valence = max(-1.0, min(1.0, state.affect_valence + affect_delta))
    new_arousal = max(0.0, min(1.0, state.affect_arousal + abs(sentiment) * 0.2))

    # Risk tolerance shifts with valence (broaden-and-build)
    risk_mod = new_valence * 0.15

    return AgentState(
        affect_valence=new_valence,
        affect_arousal=new_arousal,
        risk_tolerance_modifier=risk_mod,
        actions_taken=state.actions_taken,
    )
