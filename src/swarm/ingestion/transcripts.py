"""Earnings call transcript parser and ingestion."""

import httpx


async def fetch_transcript(symbol: str, year: int, quarter: int) -> dict | None:
    """Fetch an earnings call transcript for a given company and period.

    TODO: Integrate with a transcript provider (Financial Modeling Prep, Seeking Alpha, etc.)
    """
    # Placeholder — requires API key for a transcript provider
    return None


def extract_speaker_segments(transcript_text: str) -> list[dict]:
    """Parse a transcript into speaker-attributed segments.

    Returns a list of {speaker, role, text} dicts.
    """
    segments = []
    current_speaker = None
    current_text = []

    for line in transcript_text.split("\n"):
        stripped = line.strip()
        # Common transcript format: "Speaker Name - Title"
        if " - " in stripped and len(stripped) < 100 and not stripped[0].islower():
            if current_speaker and current_text:
                segments.append({"speaker": current_speaker, "text": " ".join(current_text)})
            parts = stripped.split(" - ", 1)
            current_speaker = parts[0].strip()
            current_text = []
        elif stripped:
            current_text.append(stripped)

    if current_speaker and current_text:
        segments.append({"speaker": current_speaker, "text": " ".join(current_text)})

    return segments
