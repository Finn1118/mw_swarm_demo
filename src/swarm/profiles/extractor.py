"""Profile extraction via Thorsten 4 API."""

from swarm.profiles.thorsten import analyze_text


async def extract_profile(executive_name: str, transcript_text: str) -> dict:
    """Extract a behavioral profile from transcript text using Thorsten 4.

    Returns the raw Thorsten 4 analysis result, which includes:
    - result.motives: power, achievement, contact scores
    - result.emotions: approach/avoidance
    - result.preferences: 4 cognitive axes
    - levels: 5-level motivation distribution
    - responses: narrative descriptions per dimension
    - candidateTexts: shorter summaries
    """
    raw = await analyze_text(transcript_text)
    return raw
