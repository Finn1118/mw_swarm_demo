"""Sample executive data with pre-built Thorsten 4 profiles."""

import json
from pathlib import Path

_PROFILES_PATH = Path(__file__).parent / "sample_profiles.json"
_API_PROFILES_PATH = Path(__file__).parent / "api_profiles.json"

SAMPLE_EXECUTIVES = [
    {
        "name": "Sundar Pichai",
        "title": "CEO",
        "company": "Google / Alphabet",
        "sector": "Technology",
    },
    {
        "name": "Alex Karp",
        "title": "CEO",
        "company": "Palantir Technologies",
        "sector": "Enterprise Software / Defense",
    },
    {
        "name": "Elon Musk",
        "title": "CEO",
        "company": "Tesla / SpaceX",
        "sector": "Automotive / Aerospace",
    },
    {
        "name": "Theodore Sarandos",
        "title": "Co-CEO",
        "company": "Netflix",
        "sector": "Entertainment / Streaming",
    },
]

# Additional executives added via Thorsten 4 API (not in sample_profiles.json)
KNOWN_EXECUTIVES = {
    "Sam Altman": {
        "name": "Sam Altman",
        "title": "CEO",
        "company": "OpenAI",
        "sector": "AI / Technology",
    },
    "Dario Amodei": {
        "name": "Dario Amodei",
        "title": "CEO",
        "company": "Anthropic",
        "sector": "AI / Technology",
    },
}

# Build unified lookup from both lists
_ALL_EXECUTIVES = {e["name"]: e for e in SAMPLE_EXECUTIVES}
_ALL_EXECUTIVES.update(KNOWN_EXECUTIVES)


def load_sample_profiles() -> dict[str, dict]:
    """Load pre-built Thorsten 4 profiles for sample executives."""
    with open(_PROFILES_PATH) as f:
        return json.load(f)


def load_api_profiles() -> dict[str, dict]:
    """Load Thorsten 4 API profiles (Sam Altman, Dario Amodei, etc.)."""
    if not _API_PROFILES_PATH.exists():
        return {}
    with open(_API_PROFILES_PATH) as f:
        return json.load(f)


def get_executive_info(name: str) -> dict | None:
    """Get metadata for any known executive by name."""
    return _ALL_EXECUTIVES.get(name)
