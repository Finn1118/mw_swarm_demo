"""Fetch and extract executive context from Wikipedia articles."""

import json

import httpx
from openai import AsyncOpenAI

from swarm.config import settings

# Wikipedia API endpoint for English Wikipedia
WIKI_API = "https://en.wikipedia.org/w/api.php"

EXTRACT_PROMPT = """\
You are analyzing a Wikipedia article about an executive to build a behavioral prediction profile.
Extract ONLY information useful for predicting how this person would act in business scenarios.

Return a concise JSON object with these fields:
{
  "full_name": "their full name including any common aliases (e.g. 'Theodore (Ted) Sarandos')",
  "current_roles": ["list of current positions and companies"],
  "career_history": ["list of key career moves, most recent first — max 8"],
  "companies_associated": ["all companies they lead, founded, or are closely tied to"],
  "key_decisions": ["major strategic decisions they've made — max 10"],
  "leadership_style": "1-2 sentence summary of their known leadership approach",
  "known_positions": ["public stances on regulation, competition, AI, etc. — max 8"],
  "notable_conflicts": ["major disputes, lawsuits, controversies — max 5"],
  "industry_relationships": ["key alliances, rivalries, board connections — max 8"]
}

Rules:
- Be factual. Only include what the article states or strongly implies.
- Keep each item to one concise sentence.
- Return valid JSON only, no markdown fences.

Wikipedia article:
{text}
"""

# Target ~3K tokens for the extracted context to keep agent prompts under 15K total
MAX_WIKI_CHARS = 40000  # Wikipedia articles can be huge; truncate input to LLM


async def fetch_wikipedia_article(name: str) -> str | None:
    """Fetch the plain-text extract of a Wikipedia article by person name.

    Uses Wikipedia's TextExtracts API to get clean plaintext.
    Returns None if no article found.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Search for the page
        search_resp = await client.get(WIKI_API, params={
            "action": "query",
            "list": "search",
            "srsearch": name,
            "srlimit": 1,
            "format": "json",
        })
        search_data = search_resp.json()
        results = search_data.get("query", {}).get("search", [])
        if not results:
            return None

        page_title = results[0]["title"]

        # Step 2: Get the full plaintext extract
        extract_resp = await client.get(WIKI_API, params={
            "action": "query",
            "titles": page_title,
            "prop": "extracts",
            "explaintext": True,
            "exsectionformat": "plain",
            "format": "json",
        })
        pages = extract_resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract:
                return extract

    return None


async def extract_executive_context(wiki_text: str) -> dict:
    """Use LLM to extract prediction-relevant info from a Wikipedia article.

    Returns a structured dict of executive context.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    truncated = wiki_text[:MAX_WIKI_CHARS]

    response = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        max_completion_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(text=truncated),
            }
        ],
    )
    raw = response.choices[0].message.content
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


async def get_wiki_context(name: str) -> dict | None:
    """Full pipeline: fetch Wikipedia article → extract executive context.

    Returns structured context dict or None if no article found.
    """
    article = await fetch_wikipedia_article(name)
    if not article:
        return None
    return await extract_executive_context(article)
